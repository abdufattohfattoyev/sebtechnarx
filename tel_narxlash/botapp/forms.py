# forms.py - TO'LIQ BULK GENERATE FORM
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import (
    iPhoneModel, StorageOption, Color,
    BatteryRange, ReplacedPart, ReplacedPartCombination, PriceEntry
)


class BulkGenerateCompleteForm(forms.Form):
    """
    Avtomatik ko'plab narxlar yaratish - BARCHA HOLATLAR UCHUN:
    1. Yangi telefon (qism yo'q)
    2. Kombinatsiyalar
    3. Alohida qismlar (1 ta)
    """

    model = forms.ModelChoiceField(
        queryset=iPhoneModel.objects.filter(is_active=True),
        label=_("iPhone Model"),
        required=True,
        help_text=_("Qaysi model uchun narxlar yaratilsin?"),
        empty_label=_("Model tanlang...")
    )

    storages = forms.ModelMultipleChoiceField(
        queryset=StorageOption.objects.none(),
        label=_("Xotira hajmlari"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Barcha kerakli xotiralarni tanlang")
    )

    colors = forms.ModelMultipleChoiceField(
        queryset=Color.objects.none(),
        label=_("Ranglar"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Barcha kerakli ranglarni tanlang")
    )

    batteries = forms.ModelMultipleChoiceField(
        queryset=BatteryRange.objects.none(),
        label=_("Batareya holatlari"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Barcha kerakli batareya holatlarini tanlang")
    )

    sim_types = forms.MultipleChoiceField(
        choices=iPhoneModel.SIM_TYPE_CHOICES,
        label=_("SIM turlari"),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        initial=['physical'],
        help_text=_("Kerakli SIM turlarini tanlang")
    )

    box_options = forms.MultipleChoiceField(
        choices=(('yes', 'Quti bor'), ('no', 'Quti yo\'q')),
        label=_("Quti holatlari"),
        widget=forms.CheckboxSelectMultiple,
        initial=['yes', 'no'],
        required=True,
        help_text=_("Quti bor/yo'q variantlarini tanlang")
    )

    # YANGI: Kombinatsiyalar va alohida qismlar
    include_clean = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Yangi telefon (qism yo'q)"),
        help_text=_("Hech qanday qism almashtirilmagan telefonlar")
    )

    combinations = forms.ModelMultipleChoiceField(
        queryset=ReplacedPartCombination.objects.none(),
        label=_("Kombinatsiyalar"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Qaysi kombinatsiyalar uchun narx yaratilsin? (2-3 talik)")
    )

    individual_parts = forms.ModelMultipleChoiceField(
        queryset=ReplacedPart.objects.none(),
        label=_("Alohida qismlar (1 ta)"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Faqat 1 ta qism almashgan telefonlar uchun")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        initial_model = None
        if 'initial' in kwargs and 'model' in kwargs['initial']:
            initial_model = kwargs['initial']['model']

        if 'model' in self.data:
            try:
                model_id = int(self.data.get('model'))
                initial_model = model_id
            except (ValueError, TypeError):
                pass

        if initial_model:
            try:
                self.fields['storages'].queryset = StorageOption.objects.filter(
                    model_id=initial_model
                ).order_by('size')

                self.fields['colors'].queryset = Color.objects.filter(
                    model_id=initial_model
                ).order_by('name')

                self.fields['batteries'].queryset = BatteryRange.objects.filter(
                    model_id=initial_model
                ).order_by('-min_percent')

                # Kombinatsiyalar
                self.fields['combinations'].queryset = ReplacedPartCombination.objects.filter(
                    model_id=initial_model,
                    is_active=True
                ).order_by('-priority')

                # Alohida qismlar
                self.fields['individual_parts'].queryset = ReplacedPart.objects.filter(
                    model_id=initial_model,
                    is_active=True
                ).order_by('order')

                if self.data and 'generate' in self.data:
                    self.fields['storages'].required = True
                    self.fields['colors'].required = True
                    self.fields['batteries'].required = True

            except (ValueError, TypeError):
                pass