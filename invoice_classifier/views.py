from django.shortcuts import render


def index(request):
    return render(request, "invoice_classifier/index.html")
