# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\admin\Desktop\沉鱼AI畅聊助手_正式版\server')
import os, traceback
os.environ['ZHIPU_API_KEY'] = os.environ.get('ZHIPU_API_KEY', '')

print("=== Test 1: NER Extraction ===")
try:
    from app import extract_key_info_from_memory
    result = extract_key_info_from_memory(user_id=23, target_id=None)
    print(f"NER Result: {result}")
except Exception as e:
    print(f"NER Error: {e}")
    traceback.print_exc()

print("\n=== Test 2: call_ai_api ===")
try:
    from app import call_ai_api
    result = call_ai_api('social', '女朋友', '', '', '今天加班好累啊', '', None)
    print(f"AI Result type: {type(result)}")
    print(f"AI Result: {result}")
except Exception as e:
    print(f"AI Error: {e}")
    traceback.print_exc()
