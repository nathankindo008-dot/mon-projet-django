from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
import hashlib

from indicateurs.models import (
    Indicateur, DonneeCollectee, MetadonneeIndicateur, Pays, Utilisateur,
)


# UTILITAIRES

def _legacy_sha256(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, stored_hash):
    """Vérifie le mot de passe : essaie d'abord PBKDF2 (Django), puis SHA-256 (legacy)."""
    if check_password(password, stored_hash):
        return True
    if stored_hash == _legacy_sha256(password):
        return True
    return False


def needs_rehash(stored_hash):
    """True si le hash est un ancien SHA-256 (64 hex chars) et pas un hash Django."""
    return len(stored_hash) == 64 and not stored_hash.startswith('pbkdf2_')


def get_utilisateur_connecte(request):
    user_id = request.session.get('utilisateur_id')
    if user_id:
        try:
            return Utilisateur.objects.get(id=user_id, actif=True)
        except Utilisateur.DoesNotExist:
            pass
    return None


def login_required_custom(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('utilisateur_id'):
            messages.error(request, "Veuillez vous connecter pour accéder à cette page.")
            return redirect('agents:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        user = get_utilisateur_connecte(request)
        if not user:
            return redirect('agents:login')
        if user.role != 'admin':
            messages.error(request, "Accès réservé aux administrateurs.")
            return redirect('agents:dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# AUTHENTIFICATION

def login_view(request):
    if request.session.get('utilisateur_id'):
        return redirect('agents:dashboard')

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        try:
            user = Utilisateur.objects.get(email=email, actif=True)
            if verify_password(password, user.mot_de_passe_hash):
                if needs_rehash(user.mot_de_passe_hash):
                    user.mot_de_passe_hash = make_password(password)
                    user.save(update_fields=['mot_de_passe_hash'])

                request.session['utilisateur_id'] = user.id
                request.session['utilisateur_nom'] = f"{user.prenom} {user.nom}"
                request.session['utilisateur_role'] = user.role
                Utilisateur.objects.filter(id=user.id).update(
                    derniere_connexion=timezone.now()
                )
                messages.success(request, f"Bienvenue, {user.prenom} !")
                return redirect('agents:dashboard')
            else:
                messages.error(request, "Email ou mot de passe incorrect.")
        except Utilisateur.DoesNotExist:
            messages.error(request, "Email ou mot de passe incorrect.")

    return render(request, 'agents/login.html')


def logout_view(request):
    request.session.flush()
    messages.success(request, "Vous avez été déconnecté.")
    return redirect('public:accueil')


# DASHBOARD AGENT

@login_required_custom
def dashboard(request):
    user = get_utilisateur_connecte(request)
    pays = Pays.objects.get(code_iso='CIV')

    mes_donnees = DonneeCollectee.objects.filter(utilisateur=user)
    stats = {
        'total':     mes_donnees.count(),
        'brouillon': mes_donnees.filter(statut='brouillon').count(),
        'soumis':    mes_donnees.filter(statut='soumis').count(),
        'valide':    mes_donnees.filter(statut='valide').count(),
        'rejete':    mes_donnees.filter(statut='rejete').count(),
    }

    total_ind     = Indicateur.objects.filter(actif=True).count()
    total_saisis  = DonneeCollectee.objects.filter(
        pays=pays, statut='valide'
    ).values('indicateur').distinct().count()
    taux = round(total_saisis * 100 / total_ind, 1) if total_ind else 0

    dernieres = mes_donnees.select_related('indicateur')\
                           .order_by('-modifie_le')[:10]

    rejetes = mes_donnees.filter(statut='rejete')\
                         .select_related('indicateur')\
                         .order_by('-modifie_le')[:5]

    context = {
        'user':          user,
        'stats':         stats,
        'taux':          taux,
        'total_ind':     total_ind,
        'total_saisis':  total_saisis,
        'dernieres':     dernieres,
        'rejetes':       rejetes,
    }
    return render(request, 'agents/dashboard.html', context)


@login_required_custom
def saisie(request, ind_id=None):
    user = get_utilisateur_connecte(request)
    pays = Pays.objects.get(code_iso='CIV')

    indicateur_selectionne = None
    if ind_id:
        indicateur_selectionne = get_object_or_404(Indicateur, pk=ind_id, actif=True)

    if request.method == 'POST':
        ind_id_post      = request.POST.get('indicateur_id')
        annee            = request.POST.get('annee_reference')
        valeur_num       = request.POST.get('valeur_numerique') or None
        valeur_txt       = request.POST.get('valeur_texte') or None
        unite            = request.POST.get('unite_saisie') or None
        source_d         = request.POST.get('source_donnee') or None
        methode          = request.POST.get('methode_collecte') or None
        commentaire      = request.POST.get('commentaire') or None
        action           = request.POST.get('action', 'brouillon')

        statut = 'soumis' if action == 'soumettre' else 'brouillon'

        try:
            indicateur = Indicateur.objects.get(pk=ind_id_post)

            existante = DonneeCollectee.objects.filter(
                indicateur=indicateur,
                pays=pays,
                annee_reference=annee
            ).first()

            if existante:
                if existante.statut == 'valide':
                    messages.error(
                        request,
                        f"Une donnée validée existe déjà pour cet indicateur en {annee}. "
                        "Seul un administrateur peut la modifier."
                    )
                    return redirect('agents:saisie_indicateur', ind_id=indicateur.pk)

                if existante.statut == 'soumis' and existante.utilisateur_id != user.id:
                    messages.warning(
                        request,
                        f"Une donnée a déjà été soumise pour {annee} par "
                        f"{existante.utilisateur.prenom} {existante.utilisateur.nom}. "
                        "Elle est en attente de validation."
                    )
                    return redirect('agents:saisie_indicateur', ind_id=indicateur.pk)

                if existante.utilisateur_id != user.id and user.role != 'admin':
                    messages.error(
                        request,
                        f"Cette donnée appartient à un autre agent "
                        f"({existante.utilisateur.prenom} {existante.utilisateur.nom}). "
                        "Vous ne pouvez pas la modifier."
                    )
                    return redirect('agents:saisie_indicateur', ind_id=indicateur.pk)

                existante.valeur_numerique = valeur_num
                existante.valeur_texte     = valeur_txt
                existante.unite_saisie     = unite
                existante.source_donnee    = source_d
                existante.methode_collecte = methode
                existante.commentaire      = commentaire
                existante.statut           = statut
                if existante.utilisateur_id == user.id:
                    existante.save()
                else:
                    existante.utilisateur = user
                    existante.save()
                messages.success(request, f"Donnée mise à jour ({statut}).")
            else:
                DonneeCollectee.objects.create(
                    indicateur       = indicateur,
                    pays             = pays,
                    utilisateur      = user,
                    annee_reference  = annee,
                    valeur_numerique = valeur_num,
                    valeur_texte     = valeur_txt,
                    unite_saisie     = unite,
                    source_donnee    = source_d,
                    methode_collecte = methode,
                    commentaire      = commentaire,
                    statut           = statut,
                )
                messages.success(request, f"Donnée enregistrée ({statut}).")

            if action == 'soumettre':
                return redirect('agents:mes_donnees')
            return redirect('agents:saisie_indicateur', ind_id=indicateur.pk)

        except Indicateur.DoesNotExist:
            messages.error(request, "Indicateur introuvable.")
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {e}")

    indicateurs = Indicateur.objects.filter(actif=True).order_by('source', 'etage', 'nom')

    donnee_existante = None
    if indicateur_selectionne:
        donnee_existante = DonneeCollectee.objects.filter(
            indicateur=indicateur_selectionne,
            pays=pays
        ).order_by('-annee_reference').first()

    annee_courante = timezone.now().year

    context = {
        'user':                    user,
        'indicateurs':             indicateurs,
        'indicateur_selectionne':  indicateur_selectionne,
        'donnee_existante':        donnee_existante,
        'annee_courante':          annee_courante,
    }
    return render(request, 'agents/saisie.html', context)


@login_required_custom
def mes_donnees(request):
    user    = get_utilisateur_connecte(request)
    donnees = DonneeCollectee.objects.filter(
        utilisateur=user
    ).select_related('indicateur', 'pays').order_by('-modifie_le')

    statut    = request.GET.get('statut', '')
    recherche = request.GET.get('q', '')
    if statut:
        donnees = donnees.filter(statut=statut)
    if recherche:
        donnees = donnees.filter(indicateur__nom__icontains=recherche)

    paginator = Paginator(donnees, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'user':     user,
        'page_obj': page_obj,
        'statut':   statut,
        'recherche':recherche,
    }
    return render(request, 'agents/mes_donnees.html', context)


# ADMIN — VALIDATION

@admin_required
def validation(request):
    user    = get_utilisateur_connecte(request)
    donnees = DonneeCollectee.objects.filter(
        statut='soumis'
    ).select_related('indicateur', 'pays', 'utilisateur').order_by('cree_le')

    paginator = Paginator(donnees, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'user':     user,
        'page_obj': page_obj,
        'total':    donnees.count(),
    }
    return render(request, 'agents/validation.html', context)


@admin_required
def valider_donnee(request, pk):
    user   = get_utilisateur_connecte(request)
    donnee = get_object_or_404(DonneeCollectee, pk=pk, statut='soumis')
    DonneeCollectee.objects.filter(pk=pk).update(
        statut    = 'valide',
        valide_par= user.id,
        valide_le = timezone.now(),
    )
    messages.success(request, "Donnée validée avec succès.")
    return redirect('agents:validation')


@admin_required
def rejeter_donnee(request, pk):
    if request.method == 'POST':
        user        = get_utilisateur_connecte(request)
        donnee      = get_object_or_404(DonneeCollectee, pk=pk)
        motif       = request.POST.get('motif', '')
        DonneeCollectee.objects.filter(pk=pk).update(
            statut     = 'rejete',
            motif_rejet= motif,
            valide_par = user.id,
            valide_le  = timezone.now(),
        )
        messages.success(request, "Donnée rejetée.")
    return redirect('agents:validation')


@admin_required
def supprimer_donnee(request, pk):
    if request.method == 'POST':
        donnee = get_object_or_404(DonneeCollectee, pk=pk)
        info = f"{donnee.indicateur.nom[:40]} — {donnee.annee_reference}"
        donnee.delete()
        messages.success(request, f"Donnée supprimée : {info}")
    redirect_to = request.POST.get('redirect', 'agents:validation')
    if redirect_to == 'agents:mes_donnees':
        return redirect('agents:mes_donnees')
    return redirect('agents:validation')


# ADMIN — GESTION DES AGENTS

@admin_required
def liste_agents(request):
    user = get_utilisateur_connecte(request)
    agents = Utilisateur.objects.all().select_related('pays').order_by('-cree_le')

    recherche = request.GET.get('q', '')
    filtre_role = request.GET.get('role', '')
    if recherche:
        agents = agents.filter(
            Q(nom__icontains=recherche) |
            Q(prenom__icontains=recherche) |
            Q(email__icontains=recherche) |
            Q(institution__icontains=recherche)
        )
    if filtre_role:
        agents = agents.filter(role=filtre_role)

    context = {
        'user': user,
        'agents_list': agents,
        'recherche': recherche,
        'filtre_role': filtre_role,
        'total': agents.count(),
    }
    return render(request, 'agents/liste_agents.html', context)


@admin_required
def creer_agent(request):
    user = get_utilisateur_connecte(request)
    pays_list = Pays.objects.filter(actif=True).order_by('nom')

    if request.method == 'POST':
        nom         = request.POST.get('nom', '').strip()
        prenom      = request.POST.get('prenom', '').strip()
        email       = request.POST.get('email', '').strip()
        password    = request.POST.get('password', '')
        institution = request.POST.get('institution', '').strip()
        pays_id     = request.POST.get('pays')
        role        = request.POST.get('role', 'collecteur')

        if not all([nom, prenom, email, password]):
            messages.error(request, "Tous les champs obligatoires doivent être remplis.")
        elif Utilisateur.objects.filter(email=email).exists():
            messages.error(request, "Un compte avec cet email existe déjà.")
        else:
            Utilisateur.objects.create(
                nom=nom,
                prenom=prenom,
                email=email,
                mot_de_passe_hash=make_password(password),
                institution=institution or None,
                pays_id=int(pays_id) if pays_id else None,
                role=role,
                actif=True,
            )
            messages.success(request, f"Agent {prenom} {nom} créé avec succès.")
            return redirect('agents:liste_agents')

    context = {
        'user': user,
        'pays_list': pays_list,
        'mode': 'creer',
    }
    return render(request, 'agents/form_agent.html', context)


@admin_required
def modifier_agent(request, pk):
    user = get_utilisateur_connecte(request)
    agent = get_object_or_404(Utilisateur, pk=pk)
    pays_list = Pays.objects.filter(actif=True).order_by('nom')

    if request.method == 'POST':
        agent.nom         = request.POST.get('nom', '').strip()
        agent.prenom      = request.POST.get('prenom', '').strip()
        agent.email       = request.POST.get('email', '').strip()
        agent.institution = request.POST.get('institution', '').strip() or None
        pays_id           = request.POST.get('pays')
        agent.pays_id     = int(pays_id) if pays_id else None
        agent.role        = request.POST.get('role', 'collecteur')
        agent.actif       = request.POST.get('actif') == 'on'

        new_password = request.POST.get('password', '').strip()
        if new_password:
            agent.mot_de_passe_hash = make_password(new_password)

        doublon = Utilisateur.objects.filter(email=agent.email).exclude(pk=pk).exists()
        if doublon:
            messages.error(request, "Un autre compte utilise déjà cet email.")
        else:
            agent.save()
            messages.success(request, f"Agent {agent.prenom} {agent.nom} modifié.")
            return redirect('agents:liste_agents')

    context = {
        'user': user,
        'agent': agent,
        'pays_list': pays_list,
        'mode': 'modifier',
    }
    return render(request, 'agents/form_agent.html', context)


@admin_required
def supprimer_agent(request, pk):
    user = get_utilisateur_connecte(request)
    agent = get_object_or_404(Utilisateur, pk=pk)

    if agent.id == user.id:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('agents:liste_agents')

    if request.method == 'POST':
        nom_complet = f"{agent.prenom} {agent.nom}"
        nb_donnees = DonneeCollectee.objects.filter(utilisateur=agent).count()
        nb_validations = DonneeCollectee.objects.filter(valide_par=agent).count()

        if nb_donnees or nb_validations:
            DonneeCollectee.objects.filter(utilisateur=agent).update(utilisateur=user)
            DonneeCollectee.objects.filter(valide_par=agent).update(valide_par=user)
            messages.info(
                request,
                f"{nb_donnees} saisie(s) et {nb_validations} validation(s) "
                f"réassignées à votre compte."
            )

        agent.delete()
        messages.success(request, f"Agent {nom_complet} supprimé.")
        return redirect('agents:liste_agents')

    return redirect('agents:liste_agents')

# ADMIN — GESTION DES INDICATEURS

@admin_required
def gestion_indicateurs(request):
    user = get_utilisateur_connecte(request)
    indicateurs = Indicateur.objects.all().order_by('source', 'etage', 'nom')

    recherche = request.GET.get('q', '')
    filtre_source = request.GET.get('source', '')
    filtre_etage = request.GET.get('etage', '')
    filtre_actif = request.GET.get('actif', '')

    if recherche:
        indicateurs = indicateurs.filter(
            Q(nom__icontains=recherche) |
            Q(code__icontains=recherche) |
            Q(theme__icontains=recherche) |
            Q(zone_cisat__icontains=recherche)
        )
    if filtre_source:
        indicateurs = indicateurs.filter(source=filtre_source)
    if filtre_etage:
        indicateurs = indicateurs.filter(etage=filtre_etage)
    if filtre_actif == '1':
        indicateurs = indicateurs.filter(actif=True)
    elif filtre_actif == '0':
        indicateurs = indicateurs.filter(actif=False)

    paginator = Paginator(indicateurs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'user': user,
        'page_obj': page_obj,
        'total': indicateurs.count(),
        'recherche': recherche,
        'filtre_source': filtre_source,
        'filtre_etage': filtre_etage,
        'filtre_actif': filtre_actif,
    }
    return render(request, 'agents/gestion_indicateurs.html', context)


@admin_required
def modifier_indicateur(request, pk):
    user = get_utilisateur_connecte(request)
    indicateur = get_object_or_404(Indicateur, pk=pk)

    try:
        meta = indicateur.metadonnee
    except MetadonneeIndicateur.DoesNotExist:
        meta = None

    if request.method == 'POST':
        indicateur.nom                 = request.POST.get('nom', '').strip()
        indicateur.source              = request.POST.get('source', 'CISAT')
        indicateur.code                = request.POST.get('code', '').strip() or None
        indicateur.etage               = int(request.POST.get('etage', 1))
        indicateur.numero_cisat        = int(request.POST.get('numero_cisat')) if request.POST.get('numero_cisat') else None
        indicateur.zone_cisat          = request.POST.get('zone_cisat', '').strip() or None
        indicateur.composante_basicset = request.POST.get('composante_basicset', '').strip() or None
        indicateur.sous_composante     = request.POST.get('sous_composante', '').strip() or None
        indicateur.sujet               = request.POST.get('sujet', '').strip() or None
        indicateur.statistique         = request.POST.get('statistique', '').strip() or None
        indicateur.theme               = request.POST.get('theme', '').strip() or None
        indicateur.unite_mesure        = request.POST.get('unite_mesure', '').strip() or None
        indicateur.accord_paris        = request.POST.get('accord_paris', '').strip() or None
        indicateur.pawp_katowice       = request.POST.get('pawp_katowice', '').strip() or None
        indicateur.ref_fdes            = request.POST.get('ref_fdes', '').strip() or None
        indicateur.ref_odd             = request.POST.get('ref_odd', '').strip() or None
        indicateur.ref_sendai          = request.POST.get('ref_sendai', '').strip() or None
        indicateur.ref_unece           = request.POST.get('ref_unece', '').strip() or None
        indicateur.ref_methodo         = request.POST.get('ref_methodo', '').strip() or None
        indicateur.sources_nat         = request.POST.get('sources_nat', '').strip() or None
        indicateur.institution_focale  = request.POST.get('institution_focale', '').strip() or None
        indicateur.agregations         = request.POST.get('agregations', '').strip() or None
        indicateur.actif               = request.POST.get('actif') == 'on'

        if not indicateur.nom:
            messages.error(request, "Le nom de l'indicateur est obligatoire.")
        else:
            indicateur.save()

            meta_definition       = request.POST.get('meta_definition', '').strip() or None
            meta_pertinence       = request.POST.get('meta_pertinence', '').strip() or None
            meta_methode_calcul   = request.POST.get('meta_methode_calcul', '').strip() or None
            meta_type_source      = request.POST.get('meta_type_source_donnee', '').strip() or None
            meta_frequence        = request.POST.get('meta_frequence_maj', '').strip() or None
            meta_categorie        = request.POST.get('meta_categorie_mesure', '').strip() or None
            meta_agregations_pot  = request.POST.get('meta_agregations_potentielles', '').strip() or None

            has_meta_data = any([
                meta_definition, meta_pertinence, meta_methode_calcul,
                meta_type_source, meta_frequence, meta_categorie, meta_agregations_pot,
            ])

            if meta:
                meta.definition               = meta_definition
                meta.pertinence               = meta_pertinence
                meta.methode_calcul           = meta_methode_calcul
                meta.type_source_donnee       = meta_type_source
                meta.frequence_maj            = meta_frequence
                meta.categorie_mesure         = meta_categorie
                meta.agregations_potentielles = meta_agregations_pot
                meta.save()
            elif has_meta_data:
                MetadonneeIndicateur.objects.create(
                    indicateur               = indicateur,
                    definition               = meta_definition,
                    pertinence               = meta_pertinence,
                    methode_calcul           = meta_methode_calcul,
                    type_source_donnee       = meta_type_source,
                    frequence_maj            = meta_frequence,
                    categorie_mesure         = meta_categorie,
                    agregations_potentielles = meta_agregations_pot,
                )
                meta = indicateur.metadonnee

            messages.success(request, f"Indicateur « {indicateur.nom[:50]} » modifié.")
            return redirect('agents:gestion_indicateurs')

    context = {
        'user': user,
        'indicateur': indicateur,
        'meta': meta,
    }
    return render(request, 'agents/modifier_indicateur.html', context)
