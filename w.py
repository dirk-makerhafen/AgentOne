import requests, base64
import sys
with open(sys.argv[1], 'rb') as f:
    audio_data = f.read()

response = requests.post('http://localhost:11434/api/chat', json={
    'model': 'gemma4:26b',
    'messages': [{
        'role': 'user',
        'content': 'Transcribe this audio.',
        'image': [base64.b64encode(audio_data).decode('utf-8')]
    }]
})
print(response.text)
