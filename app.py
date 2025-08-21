from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import os
import zipfile
from PIL import Image
from werkzeug.utils import secure_filename
import tempfile
import shutil
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Allowed extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def resize_image(image_file, width, height, quality=95, preserve_aspect=False, dpi=300):
    """
    Resize a single image and return the processed image bytes.
    """
    try:
        with Image.open(image_file) as img:
            original_format = img.format
            
            if preserve_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                resized_img = img
            else:
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
            
            # Save to bytes
            img_bytes = BytesIO()
            
            if original_format == 'JPEG' or image_file.filename.lower().endswith(('.jpg', '.jpeg')):
                resized_img.save(img_bytes, 'JPEG', quality=quality, optimize=True, dpi=(dpi, dpi))
                format_ext = 'jpg'
            else:
                resized_img.save(img_bytes, 'PNG', optimize=True, dpi=(dpi, dpi))
                format_ext = 'png'
            
            img_bytes.seek(0)
            return img_bytes, resized_img.size, format_ext
            
    except Exception as e:
        return None, None, str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/resize', methods=['POST'])
def resize_images():
    if 'files' not in request.files:
        flash('No files selected')
        return redirect(url_for('index'))
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        flash('No files selected')
        return redirect(url_for('index'))
    
    # Get form data
    try:
        width = int(request.form['width'])
        height = int(request.form['height'])
        quality = int(request.form.get('quality', 95))
        dpi = int(request.form.get('dpi', 300))
        preserve_aspect = 'preserve_aspect' in request.form
    except (ValueError, KeyError):
        flash('Invalid input parameters')
        return redirect(url_for('index'))
    
    # Validate inputs
    if width <= 0 or height <= 0:
        flash('Width and height must be positive numbers')
        return redirect(url_for('index'))
    
    if not (1 <= quality <= 100):
        flash('Quality must be between 1 and 100')
        return redirect(url_for('index'))
    
    if dpi <= 0:
        flash('DPI must be positive')
        return redirect(url_for('index'))
    
    # Process files
    processed_files = []
    errors = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Resize image
            img_bytes, new_size, format_ext = resize_image(
                file, width, height, quality, preserve_aspect, dpi
            )
            
            if img_bytes:
                # Create new filename with dimensions
                name, _ = os.path.splitext(filename)
                new_filename = f"{name}_{new_size[0]}x{new_size[1]}.{format_ext}"
                processed_files.append({
                    'filename': new_filename,
                    'data': img_bytes.getvalue(),
                    'size': new_size
                })
            else:
                errors.append(f"Error processing {filename}: {format_ext}")
    
    if not processed_files:
        flash('No images were successfully processed')
        return redirect(url_for('index'))
    
    # Create zip file if multiple images
    if len(processed_files) == 1:
        # Single file - return directly
        file_data = processed_files[0]
        return send_file(
            BytesIO(file_data['data']),
            as_attachment=True,
            download_name=file_data['filename'],
            mimetype='application/octet-stream'
        )
    else:
        # Multiple files - create zip
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_data in processed_files:
                zip_file.writestr(file_data['filename'], file_data['data'])
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'resized_images_{width}x{height}.zip',
            mimetype='application/zip'
        )

if __name__ == '__main__':
    app.run(debug=True)