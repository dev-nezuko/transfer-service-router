from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import Provider, ServiceArea
from django.core.validators import RegexValidator

phone_regex = RegexValidator(
    regex=r"^\+?1?\d{9,15}$",
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
)

class ProviderSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=254, validators=[
        UniqueValidator(
            queryset=Provider.objects.all(),
            message="A provider with this email already exists, please use a different one!",
        )
    ])
    phone = serializers.CharField(
        max_length=17,
        validators=[
            phone_regex,
            UniqueValidator(
                queryset=Provider.objects.all(),
                message="A provider with this phone number already exists, please use a different one!",
            ),
        ],
    )

    class Meta:
        model = Provider
        fields = "__all__"

class ServiceAreaSerializer(serializers.ModelSerializer):
    provider = serializers.SlugRelatedField(
        queryset=Provider.objects.all(),
        slug_field="id",
        required=True,
    )

    class Meta:
        model = ServiceArea
        fields = "__all__"
