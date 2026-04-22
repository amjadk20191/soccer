import os
import uuid
from datetime import datetime
import cv2
import numpy as np

DEFAULT_USER_IMAGE = 'users/images/Default/avatar.png'


def upload_to_model_name(instance, filename):
    model_name = instance._meta.model_name
    safe_filename = f"{uuid.uuid4().hex}{filename}"
    
    return os.path.join(
        model_name,
        datetime.now().strftime('%Y'),
        datetime.now().strftime('%m'),
        safe_filename
    )

def user_image_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f"users/images/{instance.id}/{new_filename}"

def validate_profile_image(image_file) -> tuple[bool, str]:
    """
    Validate that image contains exactly one human face.
    Returns (is_valid, error_message).
    """
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

    image_bytes = np.frombuffer(image_file.read(), np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    image_file.seek(0)

    if image is None:
        return False, 'تعذر قراءة الصورة، يرجى رفع صورة صحيحة.'

    # ✅ resize goes here — after decode, before detection
    if image.shape[1] > 640:
        scale = 640 / image.shape[1]
        image = cv2.resize(image, (640, int(image.shape[0] * scale)))

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )

    face_count = len(faces)

    if face_count == 0:
        return False, 'يجب أن تحتوي الصورة على وجه بشري واضح.'

    if face_count > 1:
        return False, f'تم اكتشاف {face_count} وجوه، يرجى رفع صورة تحتوي على وجه واحد فقط.'

    return True, ''
