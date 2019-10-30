"""dj_hetmech URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from rest_framework import routers
from dj_hetmech_app import views

router = routers.DefaultRouter()

urlpatterns = [
    path('v1/', views.api_root),
    path('v1/', include(router.urls)),
    path('v1/node/<int:pk>', views.NodeViewSet.as_view({'get': 'retrieve'}), name='node'),
    path('v1/nodes/', views.NodeViewSet.as_view({'get': 'list'}), name='nodes'),
    path('v1/nodes/other-node/<int:node>/', views.CountMetapathsToView.as_view(), name="other-node"),
    path('v1/random-node-pair/', views.RandomNodePairView.as_view(), name="random-node-pair"),
    path('v1/metapaths/source/<int:source>/target/<int:target>/', views.QueryMetapathsView.as_view(), name="metapaths"),
    path('v1/metapaths/random-nodes/', views.QueryMetapathsRandomNodesView.as_view(), name="metapaths-random-nodes"),
    path('v1/paths/source/<int:source>/target/<int:target>/metapath/<str:metapath>/', views.QueryPathsView.as_view(), name="paths"),
]
