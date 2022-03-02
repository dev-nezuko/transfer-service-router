from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testapp", "0010_default_model_ordering"),
    ]

    operations = [
        migrations.AlterField(
            model_name="servicearea",
            name="price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=6,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
    ]
