# deepseek_api.py
import requests
import json
import re
from typing import Dict, Any, List, Optional
import os

class DeepSeekNutritionAPI:
    def __init__(self, api_key=None):
        """
        Initialize DeepSeek API for nutrition analysis
        
        Args:
            api_key: DeepSeek API key (or from environment)
        """
        self.api_url = "https://api.deepseek.com/chat/completions"
        self.api_key = "sk-404f52b1127e49009596bb9dfadb3e95"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else None
        }
    
    def is_available(self):
        """Check if API is available (has API key)"""
        return self.api_key is not None and len(self.api_key) > 10
    
    def analyze_food_nutrition(self, food_name: str, portion_size: str = "normal") -> Dict[str, Any]:
        """
        Analyze nutrition using DeepSeek API
        
        Args:
            food_name: Name of the food
            portion_size: Size of portion (small, normal, large)
            
        Returns:
            Dictionary with nutrition information
        """
        if not self.is_available():
            return self.get_fallback_nutrition(food_name, portion_size)
        
        try:
            # Create prompt for nutrition analysis
            prompt = f"""Anda adalah ahli gizi. Analisis makanan ini dan kembalikan HANYA JSON mentah.

Makanan: {food_name}
Ukuran porsi: {portion_size}

Format JSON yang harus dikembalikan:
{{
    "food_name": "{food_name}",
    "portion_size": "{portion_size}",
    "calories": "xxx kcal",
    "protein": "x g",
    "fat": "x g",
    "carbs": "x g",
    "fiber": "x g",
    "sugar": "x g",
    "sodium": "x mg",
    "notes": "Catatan gizi dalam Bahasa Indonesia",
    "source": "deepseek_api"
}}

Jika tidak yakin, berikan estimasi yang masuk akal.
Pastikan semua nilai dalam string dengan unit."""

            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "Anda adalah ahli gizi profesional. Kembalikan HANYA JSON tanpa penjelasan lain."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
            
            # Remove Authorization header if no API key
            headers = {k: v for k, v in self.headers.items() if v is not None}
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Clean JSON response
                content = re.sub(r'```json|```', '', content).strip()
                
                try:
                    nutrition_data = json.loads(content)
                    
                    # Adjust for portion size
                    nutrition_data = self.adjust_for_portion(nutrition_data, portion_size)
                    
                    # Add timestamp
                    from datetime import datetime
                    nutrition_data['analyzed_at'] = datetime.now().isoformat()
                    
                    return nutrition_data
                    
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    return self.extract_nutrition_from_text(content, food_name, portion_size)
                    
            else:
                print(f"❌ API error {response.status_code}: {response.text}")
                return self.get_fallback_nutrition(food_name, portion_size)
                
        except Exception as e:
            print(f"❌ API request error: {e}")
            return self.get_fallback_nutrition(food_name, portion_size)
    
    def adjust_for_portion(self, nutrition_data: Dict, portion_size: str) -> Dict:
        """Adjust nutrition values based on portion size"""
        portion_factors = {
            "small": 0.7,
            "normal": 1.0,
            "large": 1.3,
            "kecil": 0.7,
            "sedang": 1.0,
            "besar": 1.3
        }
        
        factor = portion_factors.get(portion_size.lower(), 1.0)
        
        if factor != 1.0:
            # Fields to adjust
            nutrient_fields = ['calories', 'protein', 'fat', 'carbs', 'fiber', 'sugar']
            
            for field in nutrient_fields:
                if field in nutrition_data:
                    value_str = nutrition_data[field]
                    # Extract number
                    numbers = re.findall(r'\d+\.?\d*', value_str)
                    if numbers:
                        number = float(numbers[0])
                        unit = value_str.replace(numbers[0], '').strip()
                        adjusted_number = number * factor
                        nutrition_data[field] = f"{adjusted_number:.1f} {unit}"
        
        return nutrition_data
    
    def extract_nutrition_from_text(self, text: str, food_name: str, portion_size: str) -> Dict[str, Any]:
        """Extract nutrition information from text response"""
        result = {
            "food_name": food_name,
            "portion_size": portion_size,
            "calories": "200 kcal",
            "protein": "10 g",
            "fat": "5 g",
            "carbs": "25 g",
            "fiber": "3 g",
            "sugar": "5 g",
            "sodium": "200 mg",
            "notes": f"Analisis untuk {food_name} (porsi {portion_size})",
            "source": "text_extraction",
            "analyzed_at": datetime.now().isoformat()
        }
        
        # Try to extract values using regex
        patterns = {
            'calories': r'(\d+)\s*kcal|kalori.*?(\d+)',
            'protein': r'protein.*?(\d+\.?\d*)\s*g',
            'fat': r'fat.*?(\d+\.?\d*)\s*g|lemak.*?(\d+\.?\d*)\s*g',
            'carbs': r'carbs.*?(\d+\.?\d*)\s*g|karbohidrat.*?(\d+\.?\d*)\s*g',
            'fiber': r'fiber.*?(\d+\.?\d*)\s*g|serat.*?(\d+\.?\d*)\s*g',
            'sugar': r'sugar.*?(\d+\.?\d*)\s*g|gula.*?(\d+\.?\d*)\s*g'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Get the first non-None group
                value = next((g for g in match.groups() if g is not None), None)
                if value:
                    result[field] = f"{value} {'kcal' if field == 'calories' else 'g'}"
        
        return result
    
    def get_fallback_nutrition(self, food_name: str, portion_size: str) -> Dict[str, Any]:
        """Fallback nutrition data when API fails"""
        from datetime import datetime
        
        # Basic estimation based on food type
        food_lower = food_name.lower()
        
        if any(word in food_lower for word in ['nasi', 'rice', 'roti', 'bread', 'mie', 'noodle']):
            base = {"calories": "250", "protein": "8", "fat": "5", "carbs": "45"}
        elif any(word in food_lower for word in ['ayam', 'chicken', 'daging', 'meat', 'ikan', 'fish']):
            base = {"calories": "200", "protein": "25", "fat": "10", "carbs": "0"}
        elif any(word in food_lower for word in ['sayur', 'vegetable', 'salad', 'buah', 'fruit']):
            base = {"calories": "80", "protein": "3", "fat": "1", "carbs": "15"}
        elif any(word in food_lower for word in ['goreng', 'fried', 'krispi']):
            base = {"calories": "300", "protein": "15", "fat": "20", "carbs": "20"}
        else:
            base = {"calories": "200", "protein": "10", "fat": "8", "carbs": "25"}
        
        # Adjust for portion
        portion_factors = {"small": 0.7, "kecil": 0.7, "normal": 1.0, "sedang": 1.0, "large": 1.3, "besar": 1.3}
        factor = portion_factors.get(portion_size.lower(), 1.0)
        
        return {
            "food_name": food_name,
            "portion_size": portion_size,
            "calories": f"{float(base['calories']) * factor:.0f} kcal",
            "protein": f"{float(base['protein']) * factor:.0f} g",
            "fat": f"{float(base['fat']) * factor:.0f} g",
            "carbs": f"{float(base['carbs']) * factor:.0f} g",
            "fiber": f"{3 * factor:.0f} g",
            "sugar": f"{5 * factor:.0f} g",
            "sodium": f"{200 * factor:.0f} mg",
            "notes": f"Estimasi untuk {food_name} (porsi {portion_size})",
            "source": "fallback_estimation",
            "analyzed_at": datetime.now().isoformat()
        }
    
    def analyze_multiple_foods(self, food_predictions: List[tuple]) -> Dict[str, Any]:
        """
        Analyze multiple food predictions and return the best one
        
        Args:
            food_predictions: List of (food_name, confidence) tuples
            
        Returns:
            Best nutrition analysis
        """
        if not food_predictions:
            return self.get_fallback_nutrition("makanan", "normal")
        
        # Try each prediction starting from highest confidence
        for food_name, confidence in food_predictions:
            if confidence > 0.3:  # Only try if confidence is reasonable
                try:
                    nutrition = self.analyze_food_nutrition(food_name)
                    nutrition['prediction_confidence'] = confidence
                    return nutrition
                except:
                    continue
        
        # If all failed, use the first prediction
        food_name = food_predictions[0][0]
        return self.analyze_food_nutrition(food_name)

# Singleton instance
nutrition_api = None

def get_nutrition_api(api_key=None):
    """Get or create nutrition API instance"""
    global nutrition_api
    if nutrition_api is None:
        nutrition_api = DeepSeekNutritionAPI(api_key)
    return nutrition_api

def extract_number(value: str) -> float:
    """Extract number from string like '250 kcal'"""
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        try:
            numbers = re.findall(r'\d+\.?\d*', value)
            return float(numbers[0]) if numbers else 0.0
        except:
            return 0.0
    
    return 0.0

if __name__ == "__main__":
    # Test the API
    api = DeepSeekNutritionAPI()
    
    if api.is_available():
        print("✅ DeepSeek API available")
        result = api.analyze_food_nutrition("nasi goreng", "normal")
        print("🧪 Test result:", json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("⚠️ DeepSeek API key not found")
        result = api.get_fallback_nutrition("nasi goreng", "normal")
        print("🧪 Fallback result:", json.dumps(result, indent=2, ensure_ascii=False))