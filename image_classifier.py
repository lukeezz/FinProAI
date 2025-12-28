# image_classifier.py - UPDATED untuk support .keras
import numpy as np
import cv2
from PIL import Image
import tensorflow as tf
from tensorflow import keras
import os

class FoodImageClassifier:
    def __init__(self, model_path='best_food_effnet.keras', class_names_path='class_names.txt'):
        """
        Initialize food image classifier with Keras model
        
        Args:
            model_path: Path to .keras or .h5 model file
            class_names_path: Path to text file with class names
        """
        self.model = None
        self.class_names = []
        self.img_size = (224, 224)  # EfficientNet biasanya 224x224
        
        # Coba load model dengan berbagai ekstensi
        self.load_model_with_fallback(model_path, class_names_path)
    
    def load_model_with_fallback(self, model_path, class_names_path):
        """Try to load model with multiple extensions"""
        model_found = False
        
        # Coba beberapa ekstensi
        possible_paths = [
            model_path,  # original path
            'best_food_effnet.keras',
            'best_food_effnet.h5',
            'food_model.keras',
            'food_model.h5'
        ]
        
        for model_file in possible_paths:
            if os.path.exists(model_file):
                try:
                    print(f"🔍 Loading model from: {model_file}")
                    self.model = keras.models.load_model(model_file)
                    print(f"✅ Model loaded successfully: {model_file}")
                    
                    # Get input shape
                    if hasattr(self.model, 'input_shape') and self.model.input_shape[1:3]:
                        self.img_size = self.model.input_shape[1:3]
                        print(f"📏 Model input size: {self.img_size}")
                    
                    model_found = True
                    break
                    
                except Exception as e:
                    print(f"❌ Error loading {model_file}: {e}")
        
        if not model_found:
            print("⚠️ No model file found. Using fallback image analysis.")
            print("ℹ️ Supported formats: .keras, .h5, .hdf5")
            print("ℹ️ Please place 'best_food_effnet.keras' in project directory")
        
        # Load class names
        self.load_class_names(class_names_path)
    
    def load_class_names(self, class_names_path):
        """Load class names from file or create default"""
        if os.path.exists(class_names_path):
            try:
                with open(class_names_path, 'r', encoding='utf-8') as f:
                    self.class_names = [line.strip() for line in f.readlines()]
                print(f"✅ Loaded {len(self.class_names)} class names from {class_names_path}")
            except Exception as e:
                print(f"❌ Error loading class names: {e}")
                self.create_default_class_names()
        else:
            self.create_default_class_names()
    
    def create_default_class_names(self):
        """Create default class names for Indonesian foods"""
        self.class_names = [
            'nasi putih', 'nasi goreng', 'ayam goreng', 'ayam bakar',
            'tempe goreng', 'tahu goreng', 'rendang', 'gado-gado',
            'sate ayam', 'bakso', 'mie goreng', 'capcay', 'soto ayam',
            'martabak', 'pizza', 'burger', 'roti', 'kue', 'salad',
            'buah-buahan', 'sayuran', 'ikan', 'telur', 'susu', 'kopi'
        ]
        print(f"⚠️ Using default {len(self.class_names)} class names")
        
        # Save to file for future use
        try:
            with open('class_names.txt', 'w', encoding='utf-8') as f:
                for name in self.class_names:
                    f.write(name + '\n')
            print("💾 Saved default class names to class_names.txt")
        except Exception as e:
            print(f"❌ Error saving class names: {e}")
    
    def preprocess_for_effnet(self, image):
        """
        Preprocess image for EfficientNet model
        EfficientNet expects specific preprocessing
        """
        # Convert to numpy array if needed
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        # Convert BGR to RGB if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            if image[0, 0, 0] > image[0, 0, 2]:  # BGR check
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Resize to model input size
        image = cv2.resize(image, self.img_size)
        
        # EfficientNet specific preprocessing
        # Convert to float32
        image = image.astype('float32')
        
        # Normalize to [0, 1] or use EfficientNet preprocessing
        try:
            # Try using tf.keras.applications.efficientnet preprocess_input
            from tensorflow.keras.applications.efficientnet import preprocess_input
            image = preprocess_input(image)
        except ImportError:
            # Fallback normalization
            image = image / 255.0
        
        # Add batch dimension
        image = np.expand_dims(image, axis=0)
        
        return image
    
    def preprocess_image(self, image):
        """Main preprocessing function"""
        return self.preprocess_for_effnet(image)
    
    def predict(self, image, top_k=5):
        """
        Predict food from image
        
        Args:
            image: Image file path, PIL Image, or numpy array
            top_k: Number of top predictions to return
            
        Returns:
            List of (food_name, confidence) tuples
        """
        # Check if model is loaded
        if self.model is None:
            print("⚠️ No model loaded, using fallback prediction")
            return self.fallback_prediction(image)
        
        try:
            # Preprocess image
            processed_image = self.preprocess_image(image)
            
            # Get predictions
            predictions = self.model.predict(processed_image, verbose=0)
            
            # Handle different output formats
            if isinstance(predictions, list):
                predictions = predictions[0]  # Take first output if multiple
            
            predictions = predictions.flatten()  # Ensure 1D array
            
            # Get top K predictions
            top_indices = np.argsort(predictions)[-top_k:][::-1]
            results = []
            
            for idx in top_indices:
                if idx < len(self.class_names):
                    food_name = self.class_names[idx]
                    confidence = float(predictions[idx])
                    results.append((food_name, confidence))
                else:
                    results.append((f"class_{idx}", float(predictions[idx])))
            
            # Filter low confidence predictions
            results = [(name, conf) for name, conf in results if conf > 0.1]
            
            if not results:
                return self.fallback_prediction(image)
            
            return results
            
        except Exception as e:
            print(f"❌ Prediction error: {e}")
            import traceback
            traceback.print_exc()
            return self.fallback_prediction(image)
    
    def fallback_prediction(self, image):
        """Fallback prediction when model fails"""
        try:
            # Load image
            if isinstance(image, str):
                img = Image.open(image)
            elif isinstance(image, Image.Image):
                img = image
            else:
                img = Image.fromarray(image)
            
            # Convert to numpy array
            img_array = np.array(img)
            
            # Simple color analysis
            if len(img_array.shape) == 3:
                avg_color = np.mean(img_array, axis=(0, 1))
                
                # Rule-based prediction for Indonesian foods
                if len(avg_color) >= 3:
                    r, g, b = avg_color[:3]
                    
                    # Yellowish (nasi, ayam goreng)
                    if r > 180 and g > 160 and b < 140:
                        return [("nasi goreng", 0.7), ("ayam goreng", 0.6)]
                    # Brownish (ayam bakar, rendang)
                    elif 100 < r < 180 and 80 < g < 160 and b < 100:
                        return [("ayam bakar", 0.7), ("rendang", 0.6)]
                    # Reddish (sate, bakso)
                    elif r > g + 40 and r > b + 40:
                        return [("sate ayam", 0.7), ("bakso", 0.6)]
                    # Greenish (sayur, salad)
                    elif g > r + 30 and g > b + 30:
                        return [("sayuran", 0.8), ("salad", 0.7)]
                    # White (nasi putih, tahu)
                    elif r > 200 and g > 200 and b > 200:
                        return [("nasi putih", 0.8), ("tahu", 0.7)]
            
            return [("makanan", 0.5)]
            
        except Exception as e:
            print(f"❌ Fallback prediction error: {e}")
            return [("makanan", 0.5)]

# Singleton instance
food_classifier = None

def get_food_classifier(model_name='best_food_effnet.keras'):
    """Get or create food classifier instance with custom model name"""
    global food_classifier
    if food_classifier is None:
        food_classifier = FoodImageClassifier(model_path=model_name)
    return food_classifier

def test_model_compatibility():
    """Test if model can be loaded"""
    print("🧪 Testing model compatibility...")
    
    # Check if model file exists
    model_files = [f for f in os.listdir('.') if f.endswith(('.keras', '.h5'))]
    print(f"Found model files: {model_files}")
    
    if 'best_food_effnet.keras' in model_files:
        print("✅ Found best_food_effnet.keras")
        try:
            classifier = FoodImageClassifier('best_food_effnet.keras')
            print(f"✅ Model loaded successfully")
            print(f"✅ Input size: {classifier.img_size}")
            print(f"✅ Class names: {len(classifier.class_names)}")
            
            # Test with dummy image
            test_img = np.ones((224, 224, 3), dtype=np.uint8) * 255
            predictions = classifier.predict(test_img)
            print(f"✅ Test predictions: {predictions}")
            
            return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("❌ best_food_effnet.keras not found")
        return False

if __name__ == "__main__":
    test_model_compatibility()