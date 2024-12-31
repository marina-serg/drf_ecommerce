from django.urls import path

from apps.shop.views import CategoriesView, ProductView, ProductsView, ProductsByCategoryView, ProductsBySellerView, \
    CartView, CheckoutView, ReviewView, ReviewViewID

urlpatterns = [
    path("categories/", CategoriesView.as_view()),
    path("categories/<slug:slug>/", ProductsByCategoryView.as_view()),
    path("sellers/<slug:slug>/", ProductsBySellerView.as_view()),
    path("products/", ProductsView.as_view()),
    path("products/<slug:slug>/", ProductView.as_view()),
    path("cart/", CartView.as_view()),
    path("checkout/", CheckoutView.as_view()),
    path("reviews/<slug:slug>/", ReviewView.as_view()),
    path("review/detail/<uuid:id>/", ReviewViewID.as_view()),

]
