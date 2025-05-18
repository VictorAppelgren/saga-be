from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

def home(request):
    return render(request, 'home.html', {
        'debug': settings.DEBUG
    })

@csrf_exempt
@require_http_methods(['POST'])
def chat_message(request):
    try:
        data = json.loads(request.body)
        message = data.get('message')
        
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)
            
        # Here you would typically send the message to your chat service
        # and wait for a response. For now, we'll return a mock response
        
        response = {
            'reply': 'This is a mock response. Replace with actual service integration.',
            'status': 'success'
        }
        
        return JsonResponse(response)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
