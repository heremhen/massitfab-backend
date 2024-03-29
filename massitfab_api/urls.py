from django.contrib import admin
from django.urls import path, re_path
from .views import *

app_name = 'mfApi'

urlpatterns = [
    re_path(r'^u/get/(?i)(?P<username>[a-z]+)', get_profile, name='get_profile'),
    path('u/update', update_profile, name='update_profile'),
    
    path('content/create', create_product, name='upload_content'),
    path('content/update/<int:id>', update_product, name='update_content'),
    path('content/delete/<int:id>', delete_product, name='delete_content'),
    path('content/get/<int:id>', get_product_details, name='get_content_details'),
    path('content/get', get_products, name='get_contents'),
    path('content/search', search_products, name='search_products'),

    path('u/wishlist/toggle', add_n_remove_from_wishlist, name='toggle_wishlist'),
    path('u/wishlist/getAll', get_allWishlist, name='get_allWishlist'),
    path('u/wishlist/get', get_wishlist, name='get_wishlist'),

    path('review/create/<int:product_id>', create_review, name='create_review'),
    path('review/get/<int:product_id>', get_reviews, name="get_reviews"),
    path('review/delete/<int:review_id>', delete_review, name='delete_review'),

    path('cart/toggle/<int:product_id>', add_n_remove_from_cart, name="add_n_remove_product_from_cart"),
    path('cart/checkout', checkout_cart, name='checkout_cart'), 
    path('cart/get', get_cart_details, name='get_cart_details'),

    path('category/get', get_categories, name='get_categories'),
]
