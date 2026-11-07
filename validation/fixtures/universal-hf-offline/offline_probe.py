from huggingface_hub import HfApi
from huggingface_hub.errors import OfflineModeIsEnabled

def offline_status():
    try:
        HfApi().model_info('sentence-transformers/all-MiniLM-L6-v2')
    except OfflineModeIsEnabled as error:
        return type(error).__name__
    return 'unexpected online response'
