# Streamlit Cloud Deployment Guide

## Step 1: Prepare Files

All files are saved in: outputs/app/

### Required Files:
- app.py (main application)
- requirements.txt (dependencies)
- README.md (documentation)

### Required Models:
- outputs/models/optimized/ (all .pkl files)
- outputs/models/ensemble/ (all .pkl files)
- outputs/models/scaler_phase8.pkl
- outputs/models/feature_columns.json
- outputs/models/class_mapping.json
- outputs/models/phase12_app_configuration.json

## Step 2: Upload to GitHub

1. Create new repository on GitHub
2. Upload all files from outputs/app/ folder
3. Make sure app.py is in the root directory
4. Make sure outputs/models/ folder is uploaded

## Step 3: Deploy on Streamlit Cloud

1. Go to: https://share.streamlit.io
2. Click "New app"
3. Connect your GitHub account
4. Select your repository
5. Branch: main or master
6. File path: app.py
7. Click "Deploy!"

## Step 4: Test Deployment

1. Wait for deployment to complete (~2-5 minutes)
2. Test login with: admin1 / 1234
3. Test prediction functionality
4. Test bulk upload (if NGO/Government account)

## Troubleshooting

### Models Not Loading
- Ensure outputs/models/ folder is in correct location
- Check file paths in load_ml_models() function
- Verify all .pkl files uploaded correctly

### Large Model Files
- Use Git LFS for files >100MB
- Or host models separately and download on app startup
