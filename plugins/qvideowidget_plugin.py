from PyQt5.QtDesigner import QPyDesignerCustomWidgetPlugin
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtGui import QIcon

class QVideoWidgetPlugin(QPyDesignerCustomWidgetPlugin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initialized = False

    def initialize(self, core):
        if self.initialized:
            return
        self.initialized = True

    def isInitialized(self):
        return self.initialized

    def createWidget(self, parent):
        return QVideoWidget(parent)

    def name(self):
        return "QVideoWidget"

    def group(self):
        return "Multimedia Widgets"

    def icon(self):
        return QIcon()

    def toolTip(self):
        return "A widget for displaying video"

    def whatsThis(self):
        return "QVideoWidget displays video content from QMediaPlayer"

    def isContainer(self):
        return False

    def domXml(self):
        return '''
        <ui language="c++">
            <widget class="QVideoWidget" name="videoWidget">
                <property name="geometry">
                    <rect>
                        <x>0</x>
                        <y>0</y>
                        <width>320</width>
                        <height>240</height>
                    </rect>
                </property>
            </widget>
        </ui>
        '''

    def includeFile(self):
        return "PyQt5/QtMultimediaWidgets"
