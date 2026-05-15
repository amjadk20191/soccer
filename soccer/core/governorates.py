from django.db import models
from django.utils.translation import gettext_lazy as _

class SyrianGovernorate(models.IntegerChoices):
    # --- Governorates (10-99) ---
    DAMASCUS = 1, _('دمشق')
    RURAL_DAMASCUS = 2, _('ريف دمشق')
    HOMS = 3, _('حمص')
    LATTAKIA = 4, _('اللاذقية')
    TARTUS = 5, _('طرطوس')
