import os
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  # Enable CORS for mobile app access

# Configure SQLite Database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'pigs.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload folder configuration
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Auto-create uploads directory

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Database Model
class Pig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pig_name = db.Column(db.String(100), nullable=False)
    pig_id = db.Column(db.String(100), unique=True, nullable=False)
    dob = db.Column(db.String(50), nullable=False)
    farm_name = db.Column(db.String(150), nullable=False)
    farm_address = db.Column(db.String(250), nullable=False)
    vaccinated = db.Column(db.Boolean, default=False)
    vaccine_date = db.Column(db.String(50), nullable=True)
    breed = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(250), nullable=False)  # filename

    def to_dict(self):
        # Include full URL reference for the image based on request host URL
        # host_url gives something like "http://127.0.0.1:5000/" or "http://<ip>:5000/"
        # We'll return just the relative path as per typical setups, 
        # but to have 'full image URL' we can build it conditionally or return a relative URL 
        # and let mobile prepend the base URL. For simplicity and robustness, returning a relative path.
        image_url = f"/uploads/{self.image}" if self.image else None
        
        return {
            'id': self.id,
            'pig_name': self.pig_name,
            'pig_id': self.pig_id,
            'dob': self.dob,
            'farm_name': self.farm_name,
            'farm_address': self.farm_address,
            'vaccinated': self.vaccinated,
            'vaccine_date': self.vaccine_date,
            'breed': self.breed,
            'image': image_url
        }

# Create database tables automatically
with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return "Server is LIVE 🚀"

# Endpoint to upload pig data
@app.route('/upload', methods=['POST'])
def upload_pig():
    try:
        # 1. Check if an image is part of the request
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided in request'}), 400

        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': 'Empty image filename'}), 400

        # 2. Retrieve form data
        pig_name = request.form.get('pig_name')
        pig_id = request.form.get('pig_id')
        dob = request.form.get('dob')
        farm_name = request.form.get('farm_name')
        farm_address = request.form.get('farm_address')
        vaccinated_str = request.form.get('vaccinated', 'false').lower()
        vaccinated = vaccinated_str in ['true', '1', 'yes']
        vaccine_date = request.form.get('vaccine_date')
        breed = request.form.get('breed')

        # 3. Validate required fields
        if not all([pig_name, pig_id, dob, farm_name, farm_address, breed]):
            return jsonify({'error': 'Missing required fields'}), 400

        # 4. Check for duplicate pig_id
        existing_pig = Pig.query.filter_by(pig_id=pig_id).first()
        if existing_pig:
            return jsonify({'error': 'pig_id already exists'}), 409

        # 5. Save the image safely
        filename = secure_filename(image_file.filename)
        # Prepend the pig_id to the filename to avoid collisions between multiple uploads having the same filename
        unique_filename = f"{pig_id}_{filename}"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        image_file.save(image_path)

        # 6. Store metadata in database
        new_pig = Pig(
            pig_name=pig_name,
            pig_id=pig_id,
            dob=dob,
            farm_name=farm_name,
            farm_address=farm_address,
            vaccinated=vaccinated,
            vaccine_date=vaccine_date,
            breed=breed,
            image=unique_filename
        )
        db.session.add(new_pig)
        db.session.commit()

        return jsonify({
            'message': 'Pig uploaded successfully', 
            'pig': new_pig.to_dict()
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint to get all pigs
@app.route('/pigs', methods=['GET'])
def get_pigs():
    try:
        pigs = Pig.query.all()
        # Return full image URL in JSON for each pig
        pig_list = []
        for pig in pigs:
            pig_dict = pig.to_dict()
            # If you specifically need the absolute full URL (e.g., http://host:5000/uploads/file.png)
            if pig_dict['image']:
                pig_dict['image'] = request.host_url.rstrip('/') + pig_dict['image']
            pig_list.append(pig_dict)
            
        return jsonify(pig_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint to update a pig's details
@app.route('/update/<pig_id>', methods=['PUT', 'POST'])
def update_pig(pig_id):
    try:
        pig = Pig.query.filter_by(pig_id=pig_id).first()
        if not pig:
            return jsonify({'error': 'Pig not found'}), 404

        # Update text fields if they are provided in the request
        if 'pig_name' in request.form:
            pig.pig_name = request.form['pig_name']
        if 'dob' in request.form:
            pig.dob = request.form['dob']
        if 'farm_name' in request.form:
            pig.farm_name = request.form['farm_name']
        if 'farm_address' in request.form:
            pig.farm_address = request.form['farm_address']
        if 'vaccinated' in request.form:
            vaccinated_str = request.form['vaccinated'].lower()
            pig.vaccinated = vaccinated_str in ['true', '1', 'yes']
        if 'vaccine_date' in request.form:
            pig.vaccine_date = request.form['vaccine_date']
        if 'breed' in request.form:
            pig.breed = request.form['breed']

        # Update image if a new one is provided
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename != '':
                filename = secure_filename(image_file.filename)
                unique_filename = f"{pig.pig_id}_{filename}"
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                image_file.save(image_path)
                pig.image = unique_filename

        db.session.commit()
        return jsonify({'message': 'Pig updated successfully', 'pig': pig.to_dict()}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint to search pigs
@app.route('/search', methods=['GET'])
def search_pigs():
    try:
        query = request.args.get('query', '')
        if not query:
            return jsonify([]), 200

        search_term = f"%{query}%"
        
        # Search across multiple fields (case-insensitive)
        results = Pig.query.filter(
            db.or_(
                Pig.pig_name.ilike(search_term),
                Pig.pig_id.ilike(search_term),
                Pig.farm_name.ilike(search_term),
                Pig.farm_address.ilike(search_term),
                Pig.breed.ilike(search_term)
            )
        ).all()

        pig_list = []
        for pig in results:
            pig_dict = pig.to_dict()
            if pig_dict['image']:
                pig_dict['image'] = request.host_url.rstrip('/') + pig_dict['image']
            pig_list.append(pig_dict)

        return jsonify(pig_list), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Endpoint to serve images
@app.route('/uploads/<filename>', methods=['GET'])
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Run the server on 0.0.0.0 so it's accessible from other devices on the network
    app.run(host='0.0.0.0', port=5001, debug=True)
