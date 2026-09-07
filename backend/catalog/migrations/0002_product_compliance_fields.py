from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="care_instructions",
            field=models.TextField(blank=True, verbose_name="pielęgnacja"),
        ),
        migrations.AddField(
            model_name="product",
            name="country_of_origin",
            field=models.CharField(blank=True, max_length=120, verbose_name="kraj pochodzenia"),
        ),
        migrations.AddField(
            model_name="product",
            name="manufacturer_address",
            field=models.TextField(blank=True, verbose_name="adres producenta"),
        ),
        migrations.AddField(
            model_name="product",
            name="manufacturer_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="e-mail producenta"),
        ),
        migrations.AddField(
            model_name="product",
            name="responsible_person",
            field=models.CharField(blank=True, max_length=180, verbose_name="podmiot odpowiedzialny w UE"),
        ),
        migrations.AddField(
            model_name="product",
            name="responsible_person_address",
            field=models.TextField(blank=True, verbose_name="adres podmiotu odpowiedzialnego w UE"),
        ),
        migrations.AddField(
            model_name="product",
            name="responsible_person_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="e-mail podmiotu odpowiedzialnego w UE"),
        ),
        migrations.AddField(
            model_name="product",
            name="safety_information",
            field=models.TextField(blank=True, verbose_name="informacje i ostrzeżenia dotyczące bezpieczeństwa"),
        ),
        migrations.AlterField(
            model_name="product",
            name="materials",
            field=models.CharField(blank=True, max_length=300, verbose_name="skład surowcowy"),
        ),
    ]
