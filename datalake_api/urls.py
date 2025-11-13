from django.urls import path
from .views import GrantPermissionView, RevokePermissionView, ListResourcesView, RetrieveDataView, MoneyLast5MinView, repush_transaction_view, SearchView

urlpatterns = [
    path('permissions/grant/', GrantPermissionView.as_view(), name='grant'),
    path('permissions/revoke/', RevokePermissionView.as_view(), name='revoke'),
    path('resources/', ListResourcesView.as_view(), name='resources'),
    path('data/', RetrieveDataView.as_view(), name='data'),
    path('metrics/money_last_5min/', MoneyLast5MinView.as_view(), name='money_5min'),
    path('repush/', repush_transaction_view, name='repush'),
    path('search/', SearchView.as_view(), name='search'),
]
