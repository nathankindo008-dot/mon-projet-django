from django.db import models


class Pays(models.Model):
    code_iso = models.CharField(unique=True, max_length=3)
    nom      = models.CharField(max_length=100)
    region   = models.CharField(max_length=100, blank=True, null=True)
    actif    = models.BooleanField(default=True)

    class Meta:
        managed  = False
        db_table = 'pays'

    def __str__(self):
        return self.nom


class Utilisateur(models.Model):
    ROLE_CHOICES = [('collecteur', 'Collecteur'), ('admin', 'Administrateur')]

    nom                = models.CharField(max_length=100)
    prenom             = models.CharField(max_length=100)
    email              = models.CharField(unique=True, max_length=150)
    mot_de_passe_hash  = models.CharField(max_length=255)
    institution        = models.CharField(max_length=200, blank=True, null=True)
    pays               = models.ForeignKey(Pays, models.DO_NOTHING, blank=True, null=True)
    role               = models.CharField(max_length=20, choices=ROLE_CHOICES, default='collecteur')
    actif              = models.BooleanField(default=True)
    cree_le            = models.DateTimeField(auto_now_add=True)
    derniere_connexion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = 'utilisateur'

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Indicateur(models.Model):
    SOURCE_CHOICES = [('CISAT', 'Climatique'), ('BASICSET', 'Environnemental')]
    ETAGE_CHOICES  = [(1, 'Niveau 1'), (2, 'Niveau 2'), (3, 'Niveau 3')]

    source              = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    code                = models.CharField(unique=True, max_length=50, blank=True, null=True)
    numero_cisat        = models.SmallIntegerField(blank=True, null=True)
    zone_cisat          = models.CharField(max_length=50, blank=True, null=True)
    sujet               = models.TextField(blank=True, null=True)
    composante_basicset = models.CharField(max_length=200, blank=True, null=True)
    sous_composante     = models.TextField(blank=True, null=True)
    nom                 = models.TextField()
    statistique         = models.TextField(blank=True, null=True)
    theme               = models.CharField(max_length=100, blank=True, null=True)
    etage               = models.SmallIntegerField(choices=ETAGE_CHOICES, default=1)
    unite_mesure        = models.CharField(max_length=150, blank=True, null=True)
    accord_paris        = models.CharField(max_length=100, blank=True, null=True)
    pawp_katowice       = models.TextField(blank=True, null=True)
    ref_fdes            = models.CharField(max_length=200, blank=True, null=True)
    ref_odd             = models.CharField(max_length=200, blank=True, null=True)
    ref_sendai          = models.CharField(max_length=200, blank=True, null=True)
    ref_unece           = models.CharField(max_length=300, blank=True, null=True)
    ref_methodo         = models.CharField(max_length=300, blank=True, null=True)
    sources_nat         = models.TextField(blank=True, null=True)
    institution_focale  = models.TextField(blank=True, null=True)
    agregations         = models.TextField(blank=True, null=True)
    actif               = models.BooleanField(default=True)

    class Meta:
        managed  = False
        db_table = 'indicateur'

    def __str__(self):
        return self.nom


class MetadonneeIndicateur(models.Model):
    indicateur               = models.OneToOneField(Indicateur, models.DO_NOTHING,
                                                    related_name='metadonnee')
    definition               = models.TextField(blank=True, null=True)
    type_source_donnee       = models.TextField(blank=True, null=True)
    frequence_maj            = models.TextField(blank=True, null=True)
    methode_calcul           = models.TextField(blank=True, null=True)
    agregations_potentielles = models.TextField(blank=True, null=True)
    cree_le                  = models.DateTimeField(auto_now_add=True)
    modifie_le               = models.DateTimeField(auto_now=True)

    class Meta:
        managed  = False
        db_table = 'metadonnee_indicateur'

    def __str__(self):
        return f"Métadonnées - {self.indicateur.nom[:50]}"


class DonneeCollectee(models.Model):
    STATUT_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('soumis',    'Soumis'),
        ('valide',    'Validé'),
        ('rejete',    'Rejeté'),
    ]

    indicateur       = models.ForeignKey(Indicateur,   models.DO_NOTHING)
    pays             = models.ForeignKey(Pays,          models.DO_NOTHING)
    utilisateur      = models.ForeignKey(Utilisateur,   models.DO_NOTHING,
                                         related_name='donnees_saisies')
    annee_reference  = models.SmallIntegerField()
    valeur_numerique = models.DecimalField(max_digits=20, decimal_places=4,
                                           blank=True, null=True)
    valeur_texte     = models.TextField(blank=True, null=True)
    unite_saisie     = models.CharField(max_length=150, blank=True, null=True)
    source_donnee    = models.TextField(blank=True, null=True)
    methode_collecte = models.CharField(max_length=300, blank=True, null=True)
    commentaire      = models.TextField(blank=True, null=True)
    statut           = models.CharField(max_length=20, choices=STATUT_CHOICES,
                                        default='brouillon')
    valide_par       = models.ForeignKey(Utilisateur, models.DO_NOTHING,
                                         db_column='valide_par',
                                         related_name='donnees_validees',
                                         blank=True, null=True)
    valide_le        = models.DateTimeField(blank=True, null=True)
    motif_rejet      = models.TextField(blank=True, null=True)
    cree_le          = models.DateTimeField(auto_now_add=True)
    modifie_le       = models.DateTimeField(auto_now=True)

    class Meta:
        managed        = False
        db_table       = 'donnee_collectee'
        unique_together = (('indicateur', 'pays', 'annee_reference'),)

    def __str__(self):
        return f"{self.indicateur.nom[:40]} — {self.pays} — {self.annee_reference}"