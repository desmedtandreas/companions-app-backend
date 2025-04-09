from .models import CodeLabel
import re

def parse_enterprise_number_dotted(enterprise_number):
    if not enterprise_number:
        return None
    # Clean the input using parse_enterprise_number
    cleaned = parse_enterprise_number(enterprise_number)
    if len(cleaned) != 10 or not cleaned.isdigit():
        return None
    
    return f"{cleaned[:4]}.{cleaned[4:7]}.{cleaned[7:]}"

def parse_enterprise_number(enterprise_number):
    if not enterprise_number:
        return None
    # Remove whitespace, 'BE' prefix, dots, dashes
    cleaned = enterprise_number.upper().strip()
    cleaned = re.sub(r'\s+', '', cleaned)         # remove all spaces/tabs
    cleaned = re.sub(r'^BE', '', cleaned)         # remove 'BE' prefix
    cleaned = re.sub(r'[\.\-]', '', cleaned)      # remove dots and dashes
    return cleaned

def resolve_label(code, category):
    try:
        return CodeLabel.objects.get(code=code, category=category).name
    except CodeLabel.DoesNotExist:
        return code