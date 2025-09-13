# Attendance System

## Deployment on Render

This application is configured for deployment on Render.com.

### Configuration Files

- **render.yaml**: Contains the service configuration for Render
  - Includes repository URL, branch, and reference configuration
  - Specifies rootDirectory to ensure requirements.txt is found
- **.python-version**: Specifies Python 3.11.4 as the runtime version
- **runtime.txt**: Explicitly tells Render to use Python 3.11.4
- **requirements.txt**: Lists all Python dependencies
- **Procfile**: Defines the web process command

### Deployment Steps

1. Push your code to GitHub
2. Connect your GitHub repository to Render
3. Render will automatically detect the render.yaml file and configure the service
4. The application will be built and deployed according to the configuration

### Troubleshooting

If you encounter deployment issues:

1. Check that requirements.txt is in the root directory
2. Ensure the Python version specified in .python-version is supported by Render
3. Verify that all dependencies in requirements.txt are compatible with the specified Python version
4. Check the Render logs for specific error messages
5. If you see "requirements.txt not found" errors, the application now includes a custom build script (build.sh) that will:
   - Debug the current directory and file structure
   - Check for requirements.txt in the current directory
   - Check for requirements.txt in the requirements directory
   - Search for requirements.txt in all subdirectories
   - As a last resort, install the required packages directly
   
   This is configured in render.yaml with an inline build script that:
    ```yaml
    buildCommand: |
      echo "Current directory: $(pwd)"
      echo "Listing files:"
      ls -la
      if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
      elif [ -f "./requirements.txt" ]; then
        pip install -r ./requirements.txt
      elif [ -f "$PWD/requirements.txt" ]; then
        pip install -r $PWD/requirements.txt
      else
        echo "Installing packages directly"
        pip install Flask==2.0.1 Werkzeug==2.0.1 Jinja2==3.0.1 click==8.0.1 itsdangerous==2.0.1 MarkupSafe==2.0.1 gunicorn==20.1.0 Flask-SQLAlchemy==2.5.1 SQLAlchemy==1.4.23
      fi
    rootDirectory: ./
    ```
6. If you see errors related to commit hashes, ensure the render.yaml file has the correct reference configuration:
   ```yaml
   repo:
     url: https://github.com/devilbeast05/attendence-system-
     branch: master
     referenceType: commit
     referenceValue: ba51f8fd24c91a74865075138ff07cf7e682a17b
   ```
   
   Note: When using `referenceType: commit`, make sure to use the exact commit hash that works with your application.