# Attendance System

## Deployment on Render

This application is configured for deployment on Render.com.

### Configuration Files

- **render.yaml**: Contains the service configuration for Render
  - Includes repository URL, branch, and reference configuration
  - Specifies rootDirectory to ensure requirements.txt is found
- **.python-version**: Specifies Python 3.11.4 as the runtime version
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
5. If you see "requirements.txt not found" errors, ensure the rootDirectory is properly set in render.yaml:
   ```yaml
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