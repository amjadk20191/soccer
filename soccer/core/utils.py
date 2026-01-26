import os
import uuid
from datetime import datetime

def upload_to_model_name(instance, filename):
    model_name = instance._meta.model_name
    safe_filename = f"{uuid.uuid4().hex}{filename}"
    
    return os.path.join(
        model_name,
        datetime.now().strftime('%Y'),
        datetime.now().strftime('%m'),
        safe_filename
    )

