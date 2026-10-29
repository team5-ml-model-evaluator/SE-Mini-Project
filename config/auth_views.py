
from django.contrib.auth import login
from django.contrib.auth.views import LoginView as DjangoLoginView

from webui.audit import record_audit


class AuditLoginView(DjangoLoginView):
    def form_valid(self, form):
        response = super().form_valid(form)

        record_audit(
            actor=self.request.user,
            action="login",
            resource=f"user:{self.request.user.pk}",
            outcome="success",
        )
        return response


    def form_invalid(self, form):
        username = self.request.POST.get("username", "")

        record_audit(
            actor=None,
            action="login",
            resource=f"username:{username}" if username else "authentication",
            outcome="failure",
        )
        return super().form_invalid(form)

