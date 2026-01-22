from django.urls import path
from . import views

urlpatterns = [
    path('book-token/', views.book_token, name='book_token'),
    path('call-next/', views.call_next_token, name='call_next_token'),
    path('free-counter/<int:counter_id>/', views.free_counter, name='free_counter'),
    path('token-status/', views.token_status, name='token_status'),

    # ✅ NEW FEATURES
    path('available-slots/', views.available_slots, name='available_slots'),
    path('cancel-token/', views.cancel_token, name='cancel_token'),
    path('reschedule-token/', views.reschedule_token, name='reschedule_token'),
    path('admin-analytics/', views.admin_analytics, name='admin_analytics'),
    path("counter-status/<int:counter_id>/", views.set_counter_status, name="set_counter_status"),
    path("counter-delay/<int:counter_id>/", views.add_counter_delay, name="add_counter_delay"),
    path("display-board/", views.display_board, name="display_board"),
    path("display-data/", views.display_data, name="display_data"),
    path("export-analytics-excel/", views.export_analytics_excel, name="export_analytics_excel"),
    path("hold-token/<int:token_id>/", views.hold_token, name="hold_token"),
    path("recall-token/<int:token_id>/", views.recall_token, name="recall_token"),
    path("skip-token/<int:token_id>/", views.skip_token, name="skip_token"),

]
