import pytesseract
from PIL import Image

def perform_ocr(image_path: str) -> str:
    """
    Extracts text from an image using Tesseract OCR.
    
    Args:
        image_path (str): The path to the image file.
        
    Returns:
        str: The extracted text from the image.
    """
    try:
        # Open the image file
        img = Image.open(image_path)
        
        # Use pytesseract to extract text
        # Make sure Tesseract is installed on your system and added to PATH
        text = pytesseract.image_to_string(img)
        
        return text.strip()
    except Exception as e:
        print(f"Error performing OCR on {image_path}: {e}")
        return ""
