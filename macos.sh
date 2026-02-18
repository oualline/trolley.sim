#!/bin/bash

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Homebrew
install_homebrew() {
    echo "Checking Homebrew"
    
    if command_exists brew; then
        echo "Homebrew already installed"
        BREW_VERSION=$(brew --version | head -n1)
        echo "$BREW_VERSION"
        return 0
    fi
    
    echo "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == 'arm64' ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    
    echo "Homebrew installed"
}

# Install Python via Homebrew
install_python() {
    echo "Checking Python Installation"
    
    # Force installation of Python 3.11 which is well-supported on macOS 10.15
    if command_exists python3.11; then
        PYTHON_VERSION=$(python3.11 --version | cut -d' ' -f2)
        echo "Python $PYTHON_VERSION found"
        return 0
    fi
    
    # Try python3 but verify it's at least 3.9
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
            echo "Python $PYTHON_VERSION found (sufficient)"
            return 0
        else
            echo "Python $PYTHON_VERSION is too old. Need 3.9+ for PyQt5 and PyObjC"
        fi
    fi
    
    echo "Installing Python 3.11 via Homebrew..."
    brew install python@3.11
    
    # Link python3.11 if needed
    brew link python@3.11 --force || true
    
    echo "Python installed"
}

# Setup virtual environment
setup_venv() {
    echo "Setting Up Virtual Environment"
    
    # Remove old venv if it exists with wrong Python version
    if [[ -d "venv" ]]; then
        VENV_PYTHON=$(venv/bin/python3 --version 2>/dev/null | cut -d' ' -f2 | cut -d. -f1-2)
        if [[ "$VENV_PYTHON" == "3.8" ]]; then
            echo "Removing old venv with Python 3.8..."
            rm -rf venv
        fi
    fi
    
    if [[ -d "venv" ]]; then
        echo "Virtual environment already exists"
    else
        echo "Creating virtual environment..."
        # Try python3.11 first, then python3
        if command_exists python3.11; then
            python3.11 -m venv venv
        else
            python3 -m venv venv
        fi
        echo "Virtual environment created"
    fi
    
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    # Verify Python version in venv
    VENV_VERSION=$(python3 --version)
    echo "Virtual environment Python: $VENV_VERSION"
}

install_python_deps() {
    echo "Installing Python Dependencies"
    
    # Ensure pip is up to date
    echo "Upgrading pip..."
    python3 -m pip install --upgrade pip
    
    # Install PyQt5 - pip will automatically use binary wheel if available
    echo "Installing PyQt5 (using binary wheel)..."
    pip install --only-binary :all: PyQt5 || pip install PyQt5
    
    echo "Installing other dependencies..."
    pip install opencv-python playsound3 pynput pyinstaller

    echo "Python dependencies installed"
}

# Main execution
echo "================================"
echo "macOS Development Setup Script"
echo "================================"
echo ""

install_homebrew
install_python  # FIXED: was "install python" (typo)
setup_venv
install_python_deps

echo ""
echo "================================"
echo "Setup Complete!"
echo "================================"
echo ""
echo "To activate the virtual environment in future sessions:"
echo "  source venv/bin/activate"
