from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="checkout_token",
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True, verbose_name="token koszyka"),
        ),
    ]
