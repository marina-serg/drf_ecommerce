from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsOwner
from apps.common.utils import set_dict_attr
from apps.profiles.models import Order, OrderItem, ShippingAddress
from apps.sellers.models import Seller
from apps.shop.filters import ProductFilter
from apps.shop.models import Category, Product, Review
from apps.shop.schema_examples import PRODUCT_PARAM_EXAMPLE
from apps.shop.serializers import CategorySerializer, ReviewSerializer, CheckoutSerializer, ToggleCartItemSerializer, \
    OrderSerializer, ProductSerializer, OrderItemSerializer, CreateReviewSerializer

tags = ["Shop"]


class CategoriesView(APIView):
    serializer_class = CategorySerializer

    @extend_schema(
        summary="Categories Fetch",
        description="""
            This endpoint returns all categories.
        """,
        tags=tags
    )
    def get(self, request, *args, **kwargs):
        categories = Category.objects.all()
        serializer = self.serializer_class(categories, many=True)
        return Response(data=serializer.data, status=200)

    @extend_schema(
        summary="Category Create",
        description="""
            This endpoint create categories.
        """,
        tags=tags
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            new_cat = Category.objects.create(**serializer.validated_data)
            serializer = self.serializer_class(new_cat)
            return Response(serializer.data, status=200)
        else:
            return Response(serializer.errors, status=400)


class ProductsByCategoryView(APIView):
    serializer_class = ProductSerializer

    @extend_schema(
        operation_id="category_products",
        summary="Category Products Fetch",
        description="""
            This endpoint returns all products in a particular category.
        """,
        tags=tags
    )
    def get(self, request, *args, **kwargs):
        category = Category.objects.get_or_none(slug=kwargs["slug"])
        if not category:
            return Response(data={"message": "Category does not exist!"}, status=404)
        products = Product.objects.select_related("category", "seller", "seller__user").filter(category=category)
        serializer = self.serializer_class(products, many=True)
        return Response(data=serializer.data, status=200)


class ProductsBySellerView(APIView):
    serializer_class = ProductSerializer

    @extend_schema(
        summary="Seller Products Fetch",
        description="""
            This endpoint returns all products in a particular seller.
        """,
        tags=tags
    )
    def get(self, request, *args, **kwargs):
        seller = Seller.objects.get_or_none(slug=kwargs["slug"])
        if not seller:
            return Response(data={"message": "Seller does not exist!"}, status=404)
        products = Product.objects.select_related("category", "seller", "seller__user").filter(seller=seller)
        serializer = self.serializer_class(products, many=True)
        return Response(data=serializer.data, status=200)


class ProductsView(APIView):
    serializer_class = ProductSerializer

    @extend_schema(
        operation_id="all_products",
        summary="Product Fetch",
        description="""
            This endpoint returns all products.
        """,
        tags=tags,
        parameters=PRODUCT_PARAM_EXAMPLE,
    )
    def get(self, request, *args, **kwargs):
        products = Product.objects.select_related("category", "seller", "seller__user").all()
        filterset = ProductFilter(request.GET, queryset=products)
        if filterset.is_valid():
            queryset = filterset.qs
            serializer = self.serializer_class(queryset, many=True)
            return Response(serializer.data)
        else:
            return Response(filterset.errors, status=400)


class ProductView(APIView):
    serializer_class = ProductSerializer

    def get_object(self, slug):
        product = Product.objects.get_or_none(slug=slug)
        return product

    @extend_schema(
        operation_id="product_detail",
        summary="Product Details Fetch",
        description="""
            This endpoint returns the details for a product via the slug.
        """,
        tags=tags
    )
    def get(self, request, *args, **kwargs):
        product = self.get_object(kwargs['slug'])
        if not product:
            return Response(data={"message": "Product does not exist!"}, status=404)
        serializer = self.serializer_class(product)
        return Response(data=serializer.data, status=200)


class CartView(APIView):
    serializer_class = OrderItemSerializer

    @extend_schema(
        summary="Cart Items Fetch",
        description="""
            This endpoint returns all items in a user cart.
        """,
        tags=tags,
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        orderitems = OrderItem.objects.filter(user=user, order=None).select_related(
            "product", "product__seller", "product__seller__user")
        serializer = self.serializer_class(orderitems, many=True)
        return Response(data=serializer.data)

    @extend_schema(
        summary="Toggle Item in cart",
        description="""
            This endpoint allows a user or guest to add/update/remove an item in cart.
            If quantity is 0, the item is removed from cart
        """,
        tags=tags,
        request=ToggleCartItemSerializer,
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = ToggleCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        quantity = data["quantity"]

        product = Product.objects.select_related("seller", "seller__user").get_or_none(slug=data["slug"])
        if not product:
            return Response({"message": "No Product with that slug"}, status=404)
        orderitem, created = OrderItem.objects.update_or_create(
            user=user,
            order_id=None,
            product=product,
            defaults={"quantity": quantity},
        )
        resp_message_substring = "Updated In"
        status_code = 200
        if created:
            status_code = 201
            resp_message_substring = "Added To"
        if orderitem.quantity == 0:
            resp_message_substring = "Removed From"
            orderitem.delete()
        data = None
        if resp_message_substring != "Removed From":
            orderitem.product = product
            serializer = self.serializer_class(orderitem)
            data = serializer.data
        return Response(data={"message": f"Item {resp_message_substring} Cart", "item": data}, status=status_code)


class CheckoutView(APIView):
    serializer_class = CheckoutSerializer

    @extend_schema(
        summary="Checkout",
        description="""
                This endpoint allows a user to create an order through which payment can then be made through.
                """,
        tags=tags,
        request=CheckoutSerializer,
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        orderitems = OrderItem.objects.filter(user=user, order=None)
        if not orderitems.exists():
            return Response({"message": "No Items in Cart"}, status=404)

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shipping_id = data.get("shipping_id")
        if shipping_id:
            shipping = ShippingAddress.objects.get_or_none(id=shipping_id)
            if not shipping:
                return Response({"message": "No shipping address with that ID"}, status=404)

        def append_shipping_details(shipping):
            fields_to_update = [
                "full_name",
                "email",
                "phone",
                "address",
                "city",
                "country",
                "zipcode",
            ]
            data = {}
            for field in fields_to_update:
                value = getattr(shipping, field)
                data[field] = value
            return data

        order = Order.objects.create(user=user, **append_shipping_details(shipping))
        orderitems.update(order=order)

        serializer = OrderSerializer(order)
        return Response(data={"message": "Checkout Successful", "item": serializer.data}, status=200)


class ReviewView(APIView):
    serializer_class = ReviewSerializer

    def get_object(self, slug):
        product = Product.objects.get_or_none(slug=slug)
        return product

    @extend_schema(
        summary="Product Reviews",
        description="""
            This endpoint returns reviews for a product via the slug.
        """,
        tags=tags
    )
    def get(self, request, *args, **kwargs):
        product = self.get_object(kwargs['slug'])
        if not product:
            return Response(data={"message": "Product does not exist!"}, status=404)
        reviews = Review.objects.filter(product=product)
        serializer = self.serializer_class(instance=reviews, many=True)
        return Response(data=serializer.data, status=200)

    @extend_schema(
        summary="Create a review",
        description="""
            This endpoint allows a user to create a review.
        """,
        tags=tags,
        request=CreateReviewSerializer,
        responses=ReviewSerializer,
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        product = self.get_object(kwargs['slug'])
        if not product:
            return Response(data={"message": "Product does not exist!"}, status=404)
        if not product.orderitem_set.filter(user=user).exists():
            return Response(data={"message": "Access denied, product not in order"}, status=403)
        if Review.objects.filter(user=request.user, product=product).exists():
            return Response(data={"message": "Access denied, review already exists"}, status=403)
        serializer = CreateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        review = Review.objects.create(user=user, product=product, **data)
        serializer = self.serializer_class(review)
        return Response(serializer.data, status=201)


class ReviewViewID(APIView):
    serializer_class = CreateReviewSerializer
    permission_classes = [IsOwner]

    def get_object(self, review_id):
        review = Review.objects.get_or_none(id=review_id)
        if review is not None:
            self.check_object_permissions(self.request, review)
        return review

    @extend_schema(
        summary="Review Fetch ID",
        description="""
            This endpoint returns a product review.
        """,
        tags=tags,
    )
    def get(self, request, *args, **kwargs):
        review = self.get_object(kwargs["id"])
        if not review:
            return Response(data={"message": "Review does not exist!"}, status=404)
        serializer = self.serializer_class(instance=review)
        return Response(data=serializer.data, status=200)

    @extend_schema(
        summary="Update Review ID",
        description="""
                This endpoint allows a user to update his/her review.
            """,
        tags=tags,
    )
    def put(self, request, *args, **kwargs):
        review = self.get_object(kwargs["id"])
        if not review:
            return Response(data={"message": "Review does not exist!"}, status=404)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        review = set_dict_attr(review, data)
        review.save()
        serializer = self.serializer_class(instance=review)
        return Response(data=serializer.data, status=200)

    @extend_schema(
        summary="Delete Review ID",
        description="""
            This endpoint allows a user to delete his/her review.
        """,
        tags=tags,
    )
    def delete(self, request, *args, **kwargs):
        review = self.get_object(kwargs["id"])
        if not review:
            return Response(data={"message": "Review does not exist!"}, status=404)
        review.delete()
        return Response(data={"message": "Review deleted successfully"}, status=200)
