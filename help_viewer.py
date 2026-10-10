#!/usr/bin/env python3
"""
help_viewer.py - Display a PDF help file, opened at a named section.

OVERVIEW
========
The help text is written in LibreOffice Writer and exported to PDF.  This
program shows that PDF in a Qt window, scrolled so that a chosen section
(for example "Easy", "Start" or "Full") is at the top of the window.

HOW SECTIONS ARE FOUND
======================
We do not search the text of the PDF for the section names.  Instead we use
the PDF's *outline* (also called *bookmarks*): the clickable table of
contents that most PDF readers show in a side panel.  Each outline entry
holds a title plus the page and position it points to, which is exactly the
information we need to jump to a section.

LibreOffice creates these outline entries automatically from the document's
headings when "Export outlines" is checked in the PDF export dialog (it is
checked by default).  Only paragraphs with an Outline level of 1-10 are
exported; the built-in "Heading 1" style has Outline level 1.
    LibreOffice PDF export options (see "Export outlines"):
        https://help.libreoffice.org/latest/en-US/text/shared/01/ref_pdf_export_general.html
    LibreOffice command-line options (for "soffice --headless --convert-to pdf"):
        https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html
    The PDF specification describes outlines in section 12.3.3 "Document Outline":
        https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf

QT MODULES USED
===============
Qt's PDF support lives in two modules, QtPdf (loading and reading a PDF) and
QtPdfWidgets (a widget that draws the pages).  They exist in Qt 6 only, so
this program needs PyQt6; PyQt5 has no equivalent.
    Qt PDF module overview:   https://doc.qt.io/qt-6/qtpdf-index.html
    PyQt6 documentation:      https://www.riverbankcomputing.com/static/Docs/PyQt6/

USAGE
=====
Command line:
    python help_viewer.py help.pdf [easy|start|full]

From your own program:
    viewer = HelpViewer("help.pdf")
    viewer.show_section("start")
"""

# sys gives us the command-line arguments (sys.argv) and sys.exit().
#   https://docs.python.org/3/library/sys.html
import sys

# QModelIndex - identifies one item in a Qt item model (used to walk the
#               bookmark tree).
#     https://doc.qt.io/qt-6/qmodelindex.html
# QPointF     - an (x, y) point with floating-point coordinates; used for the
#               position of a heading on its page.
#     https://doc.qt.io/qt-6/qpointf.html
# QTimer      - used to run code once the event loop has started.
#     https://doc.qt.io/qt-6/qtimer.html
from PyQt6.QtCore import QModelIndex, QPointF, QTimer

# QPdfDocument      - loads a PDF file and gives access to its pages.
#     https://doc.qt.io/qt-6/qpdfdocument.html
# QPdfBookmarkModel - presents the PDF's outline (bookmarks) as a tree model.
#     https://doc.qt.io/qt-6/qpdfbookmarkmodel.html
from PyQt6.QtPdf import QPdfBookmarkModel, QPdfDocument

# QPdfView - a scrollable widget that draws the pages of a QPdfDocument.
#     https://doc.qt.io/qt-6/qpdfview.html
from PyQt6.QtPdfWidgets import QPdfView

# QApplication - the application object; every Qt GUI program needs one.
#     https://doc.qt.io/qt-6/qapplication.html
# QComboBox    - the drop-down list of sections on the toolbar.
#     https://doc.qt.io/qt-6/qcombobox.html
# QMainWindow  - a top-level window with room for toolbars and a central widget.
#     https://doc.qt.io/qt-6/qmainwindow.html
# QMessageBox  - used to report a PDF that cannot be opened.
#     https://doc.qt.io/qt-6/qmessagebox.html
from PyQt6.QtWidgets import QApplication, QComboBox, QMainWindow, QMessageBox


class HelpViewer(QMainWindow):
    """
    Main window that shows a PDF and can jump to a section by name.

    The window is meant to be created once and reused: each call to
    show_section() scrolls to the requested section and brings the window
    to the front, whether it was hidden, behind other windows, or already
    visible.
    """

    def __init__(self, pdf_path: str, parent=None):
        """
        Load the PDF, index its sections, and build the window.

        :param pdf_path: Path to the help PDF exported from LibreOffice.
        :param parent:   Optional parent widget (normally your main window,
                         or None for a stand-alone window).
        """
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.resize(800, 1000)          # Initial size in pixels (width, height)

        # ------------------------------------------------------------------
        # Load the PDF
        # ------------------------------------------------------------------
        # QPdfDocument.load() reads a local file synchronously, so by the
        # time it returns the document is either Ready or in an Error state.
        # We check status() rather than comparing the returned error code
        # because it avoids depending on how PyQt6 names the "no error"
        # enum member.
        #     https://doc.qt.io/qt-6/qpdfdocument.html#load
        #     https://doc.qt.io/qt-6/qpdfdocument.html#status-prop
        self.doc = QPdfDocument(self)
        self.doc.load(pdf_path)
        if self.doc.status() != QPdfDocument.Status.Ready:
            QMessageBox.critical(self, "Help", f"Could not open {pdf_path}")

        # ------------------------------------------------------------------
        # Build a lookup table: section name -> (page number, location)
        # ------------------------------------------------------------------
        # QPdfBookmarkModel reads the outline of the document it is given.
        # We walk it once here and store the results in a plain dictionary,
        # so later jumps are a simple dictionary lookup.
        #     https://doc.qt.io/qt-6/qpdfbookmarkmodel.html#document-prop
        self.bookmarks = QPdfBookmarkModel(self)
        self.bookmarks.setDocument(self.doc)

        # Keys are lower-case section titles so that lookups ignore case
        # ("Start", "start" and "START" all match).  Dictionaries keep
        # insertion order, so the keys stay in document order, which is
        # also the order used for the toolbar drop-down below.
        #     https://docs.python.org/3/library/stdtypes.html#dict
        self.sections: dict[str, tuple[int, QPointF]] = {}
        self._collect_bookmarks(QModelIndex())  # QModelIndex() = tree root (Heading 1)

        # ------------------------------------------------------------------
        # The page display
        # ------------------------------------------------------------------
        # MultiPage mode shows all pages in one continuous scrolling column,
        # so the reader can keep scrolling from one section into the next.
        # (SinglePage mode would show only one page at a time.)
        #     https://doc.qt.io/qt-6/qpdfview.html#PageMode-enum
        # FitToWidth scales pages to the width of the window, and rescales
        # automatically when the window is resized.
        #     https://doc.qt.io/qt-6/qpdfview.html#ZoomMode-enum
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.setCentralWidget(self.view)
        #     https://doc.qt.io/qt-6/qmainwindow.html#setCentralWidget

        # ------------------------------------------------------------------
        # A toolbar drop-down so the user can switch sections
        # ------------------------------------------------------------------
        # The list is built from the bookmarks actually found in the PDF, so
        # if you add or rename sections in the LibreOffice document the menu
        # updates itself the next time the PDF is exported; no code change
        # is needed.
        #
        # currentTextChanged fires whenever the selected item changes; we
        # connect it straight to show_section(), which receives the new text.
        #     https://doc.qt.io/qt-6/qcombobox.html#currentTextChanged
        #     https://doc.qt.io/qt-6/qmainwindow.html#addToolBar-2
        self.section_box = QComboBox(self)
        self.section_box.addItems([name.title() for name in self.sections])
        self.section_box.currentTextChanged.connect(self.show_section)
        self.addToolBar("Sections").addWidget(self.section_box)

    def _collect_bookmarks(self, parent: QModelIndex) -> None:
        """
        Record the title, page and on-page position of each top-level
        (Heading 1) bookmark in self.sections.

        The outline is a tree: top-level headings (Heading 1) are children
        of the root, and lower-level headings (Heading 2, 3, ...) are
        children of the heading above them.  Only the top level is used, so
        the section list stays short; sub-headings are not visited.

        Each item in QPdfBookmarkModel carries its data under several
        "roles" (named data fields):
            Title    - the bookmark text (the heading text in LibreOffice)
            Page     - the page number, counting from 0
            Location - the (x, y) position on that page, in points
                       (1/72 inch), of the place the bookmark points to
        See the Role enum:
            https://doc.qt.io/qt-6/qpdfbookmarkmodel.html#Role-enum
        General background on Qt item models and roles:
            https://doc.qt.io/qt-6/model-view-programming.html

        :param parent: The tree node whose children should be visited.
                       Pass QModelIndex() (an "invalid" index) for the root,
                       which gives the Heading 1 entries.
        """
        model = self.bookmarks

        # PyQt6 turns C++ enums into Python enum objects.  The generic
        # QAbstractItemModel.data() call expects the role as a plain int, so
        # we pass .value to be safe.
        #     https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html
        #     https://doc.qt.io/qt-6/qabstractitemmodel.html#data
        title_role = QPdfBookmarkModel.Role.Title.value
        page_role = QPdfBookmarkModel.Role.Page.value
        loc_role = QPdfBookmarkModel.Role.Location.value

        # rowCount(parent) = number of children of this node;
        # index(row, 0, parent) = the index of one child.
        #     https://doc.qt.io/qt-6/qabstractitemmodel.html#rowCount
        #     https://doc.qt.io/qt-6/qabstractitemmodel.html#index
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)

            # Each data() call can return None if the PDF entry is
            # incomplete, so we supply a sensible default for each field.
            title = (model.data(index, title_role) or "").strip().lower()
            page = model.data(index, page_role) or 0
            location = model.data(index, loc_role) or QPointF()

            # An empty heading paragraph in the document still produces a
            # bookmark, with a blank title.  Skip it so the drop-down has no
            # blank entries.
            if not title:
                continue

            # If two headings share a title, the first one in the document
            # wins.  setdefault() only stores the value if the key is new.
            #     https://docs.python.org/3/library/stdtypes.html#dict.setdefault
            self.sections.setdefault(title, (page, location))

    def show_section(self, name: str) -> None:
        """
        Show the help window with the given section at the top.

        This is the method to call from the rest of your program, for
        example from a Help menu action or a "?" button.

        :param name: Section title as it appears in the document; case and
                     surrounding spaces are ignored.  An unknown name falls
                     back to the first page rather than raising an error, so
                     a typo never stops help from appearing.
        """
        page, location = self.sections.get(name.strip().lower(), (0, QPointF()))

        # The page navigator moves the view.  jump(page, location, zoom)
        # scrolls to the given page and position; a zoom of 0 means "leave
        # the zoom as it is", so FitToWidth stays in effect.
        #     https://doc.qt.io/qt-6/qpdfview.html#pageNavigator
        #     https://doc.qt.io/qt-6/qpdfpagenavigator.html#jump
        self.view.pageNavigator().jump(page, location, 0)

        # Keep the toolbar drop-down showing the current section.
        # Changing its text would normally emit currentTextChanged and call
        # this method again, so we block signals while we update it.
        #     https://doc.qt.io/qt-6/qobject.html#blockSignals
        #     https://doc.qt.io/qt-6/qcombobox.html#currentText-prop
        self.section_box.blockSignals(True)
        self.section_box.setCurrentText(name.strip().title())
        self.section_box.blockSignals(False)

        # Make sure the window is visible and in front of other windows.
        # raise_() has a trailing underscore because "raise" is a Python
        # keyword.  Note that some window managers (and Windows' focus-
        # stealing rules) may flash the taskbar entry instead of actually
        # moving the window to the front.
        #     https://doc.qt.io/qt-6/qwidget.html#show
        #     https://doc.qt.io/qt-6/qwidget.html#raise
        #     https://doc.qt.io/qt-6/qwidget.html#activateWindow
        self.show()
        self.raise_()
        self.activateWindow()


def main() -> None:
    """
    Command-line entry point:

        python help_viewer.py <help.pdf> [section]

    If no section is given, the viewer opens at "easy".
    """
    # sys.argv[0] is the script name, [1] the PDF path, [2] the section.
    #     https://docs.python.org/3/library/sys.html#sys.argv
    if len(sys.argv) < 2:
        print("Usage: help_viewer.py <help.pdf> [section]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    section = sys.argv[2] if len(sys.argv) > 2 else "easy"

    # Passing sys.argv lets Qt handle its own standard options, such as
    # -style or -platform.
    #     https://doc.qt.io/qt-6/qapplication.html#QApplication
    app = QApplication(sys.argv)
    viewer = HelpViewer(pdf_path)
    viewer.show()

    # The jump has to happen after the window has been laid out.  Before
    # that, the view does not yet know the size of the pages on screen, so
    # it cannot work out how far to scroll and the jump is lost.  A
    # zero-millisecond single-shot timer runs our code as soon as the event
    # loop starts, which is after the first layout pass.
    #     https://doc.qt.io/qt-6/qtimer.html#singleShot
    QTimer.singleShot(0, lambda: viewer.show_section(section))

    # Start the Qt event loop; it returns when the window is closed, and we
    # pass its exit code back to the operating system.
    #     https://doc.qt.io/qt-6/qapplication.html#exec
    sys.exit(app.exec())


# Run main() only when this file is executed directly, not when it is
# imported as a module by another program.
#     https://docs.python.org/3/library/__main__.html
if __name__ == "__main__":
    main()
