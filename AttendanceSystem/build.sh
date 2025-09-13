#!/bin/bash

# Debug information
echo "Current directory: $(pwd)"
echo "Listing directory contents:"
ls -la

# Using prebuilt wheels for dlib, no need for system dependencies
echo "Using prebuilt wheels for dlib and face_recognition..."

# Check if requirements.txt exists in current directory
if [ -f "requirements.txt" ]; then
    echo "Found requirements.txt in current directory, installing dependencies..."
    pip install -r requirements.txt
    exit 0
fi

# Check if requirements.txt exists in requirements directory
if [ -f "requirements/requirements.txt" ]; then
    echo "Found requirements.txt in requirements directory, installing dependencies..."
    pip install -r requirements/requirements.txt
    exit 0
fi

# If we get here, search for requirements.txt in all subdirectories
echo "requirements.txt not found in expected locations!"
echo "Searching for requirements.txt in all subdirectories:"
find . -name "requirements.txt" -type f

# Try to find and use requirements.txt
REQUIREMENTS_PATH=$(find . -name "requirements.txt" -type f | head -n 1)

if [ -n "$REQUIREMENTS_PATH" ]; then
    echo "Found requirements.txt at: $REQUIREMENTS_PATH"
    pip install -r "$REQUIREMENTS_PATH"
    exit 0
else
    echo "ERROR: Could not find requirements.txt anywhere!"
    
    # Last resort: manually install the required packages
    echo "Attempting to install packages directly..."
    pip install Flask==2.0.1 Werkzeug==2.0.1 Jinja2==3.0.1 click==8.0.1 itsdangerous==2.0.1 MarkupSafe==2.0.1 gunicorn==20.1.0 Flask-SQLAlchemy==2.5.1 SQLAlchemy==1.4.23 face-recognition==1.3.0 opencv-python==4.9.0.80 dlib-binary==19.24.2
    
    if [ $? -eq 0 ]; then
        echo "Successfully installed packages directly."
        exit 0
    else
        echo "Failed to install packages directly."
        exit 1
    fi
fi