Voici un README global en français et une description GitHub complète :

# 🗃️ Django Data Lake API - Skeleton

**API Django REST Framework pour la gestion centralisée de données avec contrôle d'accès granulaire**

## 📖 Description du Projet

Ce projet fournit une **API REST complète** pour gérer un data lake (lac de données) avec :
- 🔐 **Système de permissions avancé** pour contrôler l'accès aux données
- 📊 **Gestion des données métier** (transactions, produits, clients)
- 📝 **Audit automatique** de tous les accès API
- 🔍 **Filtrage et recherche avancée**
- 📚 **Documentation interactive** Swagger/Redoc
- 🏗️ **Architecture modulaire** et extensible

## 🚀 Installation Rapide

### Prérequis
- Python 3.8+
- Django 4.2+
- MySQL (optionnel, SQLite par défaut)

### Installation

```bash
# 1. Cloner le projet
git clone <votre-repo>
cd datalake_project

# 2. Créer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos paramètres

# 5. Initialiser la base de données
python manage.py migrate
python manage.py createsuperuser

# 6. Lancer le serveur
python manage.py runserver
```

## 🎯 Fonctionnalités

### 🔐 Authentification & Autorisation
- **Authentification par token**
- **Permissions granulaire** par ressource (fichier/table)
- **Rôles utilisateurs** (admin, lecture seule, écriture)
- **Logging automatique** de tous les accès

### 📊 Gestion des Données
- **API REST complète** pour transactions, produits, clients
- **Pagination automatique** (10 éléments par page)
- **Filtrage avancé** par montant, pays, catégorie, etc.
- **Projection de champs** pour optimiser les performances

### 🔍 Métriques & Analytics
- **Argent dépensé** dans les 5 dernières minutes
- **Total par utilisateur** et type de transaction
- **Top produits** les plus achetés
- **Statistiques temps-réel**

### 📝 Audit & Data Lineage
- **Versioning des données** avec historique complet
- **Tracking des accès** (qui, quand, quoi)
- **Liste des ressources** disponibles
- **Journal d'audit** consultable via l'API

### 🚀 Fonctionnalités Avancées
- **Recherche full-text** dans les données
- **RPC pour ML training** (entraînement modèles)
- **Re-push Kafka** pour reprocessing
- **API documentée** automatiquement

## 🌐 URLs Disponibles

| URL | Description |
|-----|-------------|
| `http://localhost:8000/admin/` | **Interface d'administration** Django |
| `http://localhost:8000/api/` | **API REST principale** |
| `http://localhost:8000/swagger/` | **Documentation interactive** Swagger UI |
| `http://localhost:8000/redoc/` | **Documentation alternative** Redoc |

## 🔧 Commandes Utiles

```bash
# Initialiser le data lake (structure + utilisateurs test)
python manage.py init_datalake

# Créer les migrations après modification des modèles
python manage.py makemigrations
python manage.py migrate

# Lancer les tests
python manage.py test

# Créer un superutilisateur
python manage.py createsuperuser

# Shell Django pour debug
python manage.py shell
```

## 🔌 Intégration Kafka

Le projet est conçu pour s'intégrer avec votre **kafka_project_pipeline** :

1. **Placez ce projet à côté** de votre dossier Kafka
2. **Mettez à jour** `DATA_LAKE_ROOT` dans le fichier `.env`
3. **Utilisez l'API** pour consommer/produire des données Kafka

## 🛠️ Développement

### Ajouter un nouveau modèle
1. Définir le modèle dans `datalake_api/models.py`
2. Créer le sérialiseur dans `datalake_api/serializers.py`
3. Ajouter les filtres dans `datalake_api/filters.py`
4. Créer la vue dans `datalake_api/views.py`
5. Ajouter les URLs dans `datalake_api/urls.py`

### Personnaliser les permissions
Modifiez `datalake_api/permissions.py` pour ajouter vos règles métier.

### Extension du data lake
Le système est modulaire - ajoutez facilement de nouveaux types de données et règles de gestion.

## 📊 Modèles de Données Principaux

- **Transaction** : Paiements, commandes, transactions financières
- **Product** : Catalogue produits, stocks, prix
- **Customer** : Clients, profils, historiques
- **DataLakePermission** : Contrôle d'accès aux ressources
- **APIAccessLog** : Audit des accès API

## 🤝 Contribution

1. Forkez le projet
2. Créez votre branche feature (`git checkout -b feature/AmazingFeature`)
3. Committez vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Pushez la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request


**Développé en utilisant Django REST Framework**


Ce README donne une vision complète et professionnelle de votre projet ! 🎯