from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def ui(request):
    return render(request, 'ui.html', context={'user_pk': request.user.pk})

