# from django.shortcuts import render


# from .models import Vendor
# # Create your views here.
# def vprofile(request):
#     context = {
#         'vendor': vendor
#     }
#     return render(request,'vendor/vprofile.html')


from django.shortcuts import render
from .models import Vendor

def vprofile(request):

    return render(request, 'vendor/vprofile.html')