from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Chats', '0003_message_file_message_message_type_alter_message_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]