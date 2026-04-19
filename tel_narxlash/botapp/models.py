# models.py - TO'LIQ VERSIYA (RECURSION FIX)
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class iPhoneModel(models.Model):
    SIM_TYPE_CHOICES = (
        ('physical', 'SIM karta'),
        ('esim', 'eSIM'),
        ('1imei', '1 IMEI'),
        ('2imei', '2 IMEI'),
    )

    name = models.CharField(max_length=100, unique=True, verbose_name=_("Model nomi"))
    order = models.IntegerField(default=0, verbose_name=_("Tartib raqami"))
    is_active = models.BooleanField(default=True, verbose_name=_("Faol"))

    default_sim_type = models.CharField(
        max_length=20,
        choices=SIM_TYPE_CHOICES,
        default='physical',
        verbose_name=_("Standart SIM turi"),
        help_text=_("iPhone 11-13: SIM karta, iPhone 14+: eSIM")
    )

    base_standard_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Standart narx ($)"),
        help_text=_("Eng yaxshi holat narxi DOLLAR da. Masalan: 1000.00")
    )

    box_price_difference = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=-10,
        verbose_name=_("Quti yo'q farqi ($)"),
        help_text=_("Quti yo'q bo'lsa qancha arzonroq (dollar). Masalan: -10.00")
    )

    alternative_sim_price_difference = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=-5,
        verbose_name=_("Boshqa SIM turi farqi ($)"),
        help_text=_("Standart bo'lmagan SIM (dollar). Masalan: -5.00")
    )

    uses_cycle_count = models.BooleanField(
        default=False,
        verbose_name=_("Sikl soni ishlatadi"),
        help_text=_("iPhone 17+ uchun. 100% batareyada sikl soni so'raladi.")
    )

    dual_imei_price_difference = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("2 IMEI farqi ($)"),
        help_text=_("2 IMEI modelga nisbatan 1 IMEI qancha arzon (masalan: -30)")
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order']
        verbose_name = _("iPhone Modeli")
        verbose_name_plural = _("iPhone Modellari")


class StorageOption(models.Model):
    model = models.ForeignKey(iPhoneModel, on_delete=models.CASCADE, related_name='storages', verbose_name=_("Model"))
    size = models.CharField(max_length=20, verbose_name=_("Xotira hajmi"))

    price_difference = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Narx farqi ($)"),
        help_text=_("Standart xotiraga nisbatan (dollar). Masalan: 64GB=-600")
    )
    is_standard = models.BooleanField(
        default=False,
        verbose_name=_("Standart xotira"),
        help_text=_("Bu standart (eng katta) xotira")
    )

    def __str__(self):
        return f"{self.model.name} - {self.size}"

    class Meta:
        unique_together = ('model', 'size')
        verbose_name = _("Xotira hajmi")
        verbose_name_plural = _("Xotira hajmlari")
        ordering = ['model', 'size']


class Color(models.Model):
    COLOR_TYPE_CHOICES = (
        ('standard', 'Standart'),
        ('premium', 'Premium'),
    )

    model = models.ForeignKey(iPhoneModel, on_delete=models.CASCADE, related_name='available_colors',
                              verbose_name=_("Model"))
    name = models.CharField(max_length=60, verbose_name=_("Rang nomi"))
    image = models.ImageField(upload_to='colors/', blank=True, null=True, verbose_name=_("Rang rasmi"))

    color_type = models.CharField(
        max_length=20,
        choices=COLOR_TYPE_CHOICES,
        default='standard',
        verbose_name=_("Rang turi")
    )

    price_difference = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Narx farqi ($)"),
        help_text=_("Standart rangga nisbatan (dollar). Masalan: -20")
    )

    def __str__(self):
        type_label = " (Premium)" if self.color_type == 'premium' else ""
        return f"{self.model} — {self.name}{type_label}"

    class Meta:
        unique_together = ('model', 'name')
        verbose_name = _("Rang")
        verbose_name_plural = _("Ranglar")


class BatteryRange(models.Model):
    model = models.ForeignKey(
        iPhoneModel,
        on_delete=models.CASCADE,
        related_name='battery_ranges',
        verbose_name=_("Model"),
        help_text=_("Bu batareya oraliq qaysi model uchun")
    )

    label = models.CharField(max_length=30, verbose_name=_("Oraliq nomi"))
    min_percent = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Minimal foiz"))
    max_percent = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Maksimal foiz"))
    is_cycle_range = models.BooleanField(
        default=False,
        verbose_name=_("Sikl oralig'i"),
        help_text=_("Foiz o'rniga sikl soni bo'lsa belgilang (masalan: 0-100 sikl)")
    )

    price_difference = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Narx farqi ($)"),
        help_text=_("100% ga nisbatan (dollar). Masalan: 70-74% = -300")
    )
    is_standard = models.BooleanField(
        default=False,
        verbose_name=_("Standart (100%)"),
        help_text=_("Bu standart batareya holati (100%)")
    )

    def __str__(self):
        return f"{self.model.name} - {self.label}"

    class Meta:
        ordering = ['model', '-min_percent']
        verbose_name = _("Batareya oraliq")
        verbose_name_plural = _("Batareya oraliqlar")
        unique_together = ('model', 'label')


class ReplacedPart(models.Model):
    """ALOHIDA QISMLAR - har bir qism uchun narx"""
    PART_CHOICES = (
        ('battery', 'Batareyka'),
        ('back_cover', 'Krishka'),
        ('face_id', 'Face ID'),
        ('glass', 'Oyna'),
        ('screen', 'Ekran'),
        ('camera', 'Kamera'),
        ('broken', 'Qirilgan'),
        ('body', 'Korpus'),
    )


    model = models.ForeignKey(
        iPhoneModel,
        on_delete=models.CASCADE,
        related_name='replaced_parts',
        verbose_name=_("Model")
    )

    part_type = models.CharField(
        max_length=20,
        choices=PART_CHOICES,
        verbose_name=_("Qism nomi")
    )

    price_reduction = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Alohida narx ($)"),
        help_text=_("Faqat bu qism almashgan bo'lsa. Masalan: Ekran = -100")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Ta'rif")
    )

    order = models.IntegerField(
        default=0,
        verbose_name=_("Tartib")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Faol")
    )

    def __str__(self):
        return f"{self.model.name} - {self.get_part_type_display()}: ${self.price_reduction}"

    class Meta:
        verbose_name = _("Almashgan qism (alohida)")
        verbose_name_plural = _("Almashgan qismlar (alohida)")
        ordering = ['model', 'order', 'part_type']
        unique_together = ('model', 'part_type')


class ReplacedPartCombination(models.Model):
    """KOMBINATSIYALAR - O'zingiz narx kiritasiz"""
    model = models.ForeignKey(
        iPhoneModel,
        on_delete=models.CASCADE,
        related_name='part_combinations',
        verbose_name=_("Model")
    )

    name = models.CharField(
        max_length=200,
        verbose_name=_("Kombinatsiya nomi"),
        help_text=_("Masalan: 'Ekran + Batareyka'")
    )

    parts = models.ManyToManyField(
        ReplacedPart,
        verbose_name=_("Qismlar"),
        help_text=_("Kombinatsiyaga kiruvchi qismlar (2-3 ta). ⚠️ Oyna va Ekran birgalikda BO'LMAYDI!")
    )

    custom_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Kombinatsiya narxi ($)"),
        help_text=_("Bu kombinatsiya tanlanganda QO'SHILADIGAN/AYRILADIGAN narx. Masalan: -125 yoki -200")
    )

    priority = models.IntegerField(
        default=0,
        verbose_name=_("Ustuvorlik"),
        help_text=_("3 ta qism > 2 ta qism. Yuqori raqam birinchi tekshiriladi.")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Faol")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.pk:
            parts_list = ", ".join([p.get_part_type_display() for p in self.parts.all()])
            return f"{self.model.name} - {parts_list}: ${self.custom_price}"
        return self.name

    def get_individual_total(self):
        """Alohida hisoblangan jami"""
        return sum([part.price_reduction for part in self.parts.all()])

    def get_savings(self):
        """Tejash miqdori"""
        individual = self.get_individual_total()
        return individual - self.custom_price

    class Meta:
        verbose_name = _("Qismlar kombinatsiyasi")
        verbose_name_plural = _("Qismlar kombinatsiyalari")
        ordering = ['model', '-priority', 'name']

    def clean(self):
        """Validatsiya"""
        super().clean()

        if self.pk:
            parts = self.parts.all()

            # Kamida 2 ta qism
            if parts.count() < 2:
                raise ValidationError("❌ Kombinatsiyada kamida 2 ta qism bo'lishi kerak!")

            # Maksimal 3 ta qism
            if parts.count() > 3:
                raise ValidationError("❌ Kombinatsiyada maksimal 3 ta qism bo'lishi mumkin!")

            part_types = [p.part_type for p in parts]

            # ⚠️ ASOSIY QOIDA: Oyna va Ekran bir vaqtda BO'LMAYDI
            if 'glass' in part_types and 'screen' in part_types:
                raise ValidationError(
                    "❌ XATO: Oyna va Ekran BIRGALIKDA BO'LMAYDI! "
                    "Ular FAQAT boshqa qismlar bilan ishlatiladi (lekin bir-biri bilan emas). "
                    "\n\n✅ TO'G'RI misollar:"
                    "\n• Ekran + Batareyka"
                    "\n• Oyna + Korpus"
                    "\n• Ekran + Kamera + Batareyka"
                    "\n\n❌ NOTO'G'RI:"
                    "\n• Oyna + Ekran"
                )


class PriceEntry(models.Model):
    """TELEFON NARXI - kombinatsiya yoki alohida"""
    model = models.ForeignKey(iPhoneModel, on_delete=models.CASCADE, related_name='prices', verbose_name=_("Model"))
    storage = models.ForeignKey(StorageOption, on_delete=models.PROTECT, verbose_name=_("Xotira hajmi"))
    color = models.ForeignKey(
        Color,
        on_delete=models.PROTECT,
        verbose_name=_("Rang"),
        null=True,
        blank=True
    )
    sim_type = models.CharField(
        max_length=20,
        choices=iPhoneModel.SIM_TYPE_CHOICES,
        verbose_name=_("SIM turi")
    )
    battery = models.ForeignKey(BatteryRange, on_delete=models.PROTECT, verbose_name=_("Batareya holati"))
    has_box = models.BooleanField(default=True, verbose_name=_("Quti bor"))

    # YANGI: Kombinatsiya yoki alohida qismlar
    combination = models.ForeignKey(
        ReplacedPartCombination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Kombinatsiya"),
        help_text=_("Agar telefonda qismlar kombinatsiyasi bo'lsa tanlang")
    )

    replaced_parts = models.ManyToManyField(
        ReplacedPart,
        blank=True,
        verbose_name=_("Almashgan qismlar (alohida)"),
        help_text=_("Agar kombinatsiya tanlangan bo'lsa, bu maydon ishlatilmaydi")
    )

    manual_adjustment = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Qo'lda sozlash ($)"),
        help_text=_("Maxsus hollarda qo'shimcha +/- (dollar)")
    )

    note = models.TextField(blank=True, verbose_name=_("Izoh"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Yaratilgan"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Yangilangan"))

    def calculate_price(self):
        """
        Avtomatik narx hisoblash

        ALGORITM:
        1. Standart narx
        2. + Xotira farqi
        3. + Rang farqi
        4. + Batareya farqi
        5. + Quti farqi (agar yo'q bo'lsa)
        6. + SIM farqi (agar boshqa bo'lsa)
        7. + Kombinatsiya YOKI Alohida qismlar
        8. + Qo'lda sozlash
        """
        price = self.model.base_standard_price

        if self.storage:
            price += self.storage.price_difference

        if self.color:
            price += self.color.price_difference

        if self.battery:
            price += self.battery.price_difference

        if not self.has_box:
            price += self.model.box_price_difference

        if self.sim_type != self.model.default_sim_type:
            price += self.model.alternative_sim_price_difference

        # KOMBINATSIYA yoki ALOHIDA
        if self.combination:
            # Kombinatsiya tanlangan - uning narxini qo'shish
            price += self.combination.custom_price
        else:
            # Kombinatsiya yo'q - alohida qismlarni hisoblash
            for part in self.replaced_parts.all():
                price += part.price_reduction

        price += self.manual_adjustment

        return max(price, 0)

    def get_final_price(self):
        """Yakuniy narx (dollar)"""
        return self.calculate_price()

    def get_final_price_display(self):
        """Narxni $ belgisi bilan"""
        price = self.get_final_price()
        return f"${price:,.2f}"

    def get_replaced_parts_display(self):
        """Almashgan qismlarni ko'rsatish"""
        if self.combination:
            parts = self.combination.parts.all()
            return ", ".join([part.get_part_type_display() for part in parts])

        parts = self.replaced_parts.all()
        if not parts:
            return "Yo'q"
        return ", ".join([part.get_part_type_display() for part in parts])

    def get_discount_method_display(self):
        """Qaysi usul ishlatilgan (KOMBINATSIYA yoki ALOHIDA)"""
        if self.combination:
            return f"🎯 KOMBINATSIYA: {self.combination.name}"

        if self.replaced_parts.exists():
            count = self.replaced_parts.count()
            return f"🔧 ALOHIDA ({count} ta qism)"

        return "Almashgan qism yo'q"

    def get_individual_total(self):
        """Alohida hisoblangan jami"""
        if self.combination:
            return self.combination.get_individual_total()
        return sum([part.price_reduction for part in self.replaced_parts.all()])

    def get_price_breakdown(self):
        """Narx tarkibini ko'rsatish"""
        breakdown = []

        breakdown.append(f"Standart: ${self.model.base_standard_price:,.2f}")

        if self.storage and self.storage.price_difference != 0:
            breakdown.append(f"Xotira ({self.storage.size}): ${self.storage.price_difference:+,.2f}")

        if self.color and self.color.price_difference != 0:
            breakdown.append(f"Rang ({self.color.name}): ${self.color.price_difference:+,.2f}")

        if self.battery and self.battery.price_difference != 0:
            breakdown.append(f"Batareya ({self.battery.label}): ${self.battery.price_difference:+,.2f}")

        if not self.has_box:
            breakdown.append(f"Quti yo'q: ${self.model.box_price_difference:+,.2f}")

        if self.sim_type != self.model.default_sim_type:
            sim_label = "eSIM" if self.sim_type == 'esim' else "SIM karta"
            breakdown.append(f"{sim_label}: ${self.model.alternative_sim_price_difference:+,.2f}")

        # KOMBINATSIYA yoki ALOHIDA
        if self.combination:
            parts_list = ", ".join([p.get_part_type_display() for p in self.combination.parts.all()])
            individual_total = self.combination.get_individual_total()
            breakdown.append(
                f"🎯 KOMBINATSIYA ({parts_list}): "
                f"${self.combination.custom_price:+,.2f} "
                f"[alohida: ${individual_total:+,.2f}]"
            )
        elif self.replaced_parts.exists():
            for part in self.replaced_parts.all():
                breakdown.append(f"{part.get_part_type_display()}: ${part.price_reduction:+,.2f}")

        if self.manual_adjustment != 0:
            breakdown.append(f"Qo'lda: ${self.manual_adjustment:+,.2f}")

        breakdown.append(f"= {self.get_final_price_display()}")

        return " | ".join(breakdown)

    def __str__(self):
        parts_info = self.get_replaced_parts_display()
        return f"{self.model} {self.storage} {self.color} | {parts_info} → {self.get_final_price_display()}"

    class Meta:
        verbose_name = _("Telefon narxi")
        verbose_name_plural = _("Telefon narxlari")
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """✅ RECURSION FIX - calculate_price() ni chaqirmaslik"""
        if not self.sim_type:
            self.sim_type = self.model.default_sim_type

        # calculate_price() chaqirilmaydi - u get_final_price() orqali avtomatik hisoblanadi
        # Bu recursion xatosining oldini oladi

        super().save(*args, **kwargs)

    def clean(self):
        """Validatsiya"""
        super().clean()

        # Kombinatsiya VA alohida qismlar bir vaqtda bo'lmasligi kerak
        if self.combination and self.replaced_parts.exists():
            raise ValidationError(
                "❌ Kombinatsiya va alohida qismlar bir vaqtda tanlanishi mumkin emas! "
                "Faqat birini tanlang."
            )