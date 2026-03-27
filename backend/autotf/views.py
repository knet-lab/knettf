import io

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.views import View
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

import common
from common.response import ResponseMixin
from common.permissions import check_owner
from kcore.services import UserService

from .serializers import (
    TerraformConfigListSerializer,
    TerraformConfigDetailSerializer,
    TerraformConfigCreateSerializer,
    TerraformConfigTextCreateSerializer,
    TerraformConfigUpdateSerializer,
    TerraformToolSerializer,
    ScanReportDetailSerializer,
    ScanTriggerSerializer,
)
from .services import (
    TerraformConfigService,
    TerraformToolService,
    ScanReportService,
    ScanService,
)


# ── TerraformConfig (user-scoped) ──────────────────────────────────────────────

class TerraformConfigList(APIView, ResponseMixin):
    def get(self, request: common.Request, user_pk: int):
        user = UserService.get_user_by_id(user_pk)
        check_owner(request, user.pk)
        configs = TerraformConfigService.get_configs_by_user(user)
        return self.success_response(TerraformConfigListSerializer(configs, many=True).data)

    def post(self, request: common.Request, user_pk: int):
        user = UserService.get_user_by_id(user_pk)
        check_owner(request, user.pk)
        serializer = TerraformConfigCreateSerializer(
            data=request.data, context={'owner': user})
        serializer.is_valid(raise_exception=True)
        config = TerraformConfigService.create_from_file(
            owner=user, **serializer.validated_data)
        return self.success_response(
            TerraformConfigDetailSerializer(config).data, status=status.HTTP_201_CREATED)


class TerraformConfigTextCreate(APIView, ResponseMixin):
    def post(self, request: common.Request, user_pk: int):
        user = UserService.get_user_by_id(user_pk)
        check_owner(request, user.pk)
        serializer = TerraformConfigTextCreateSerializer(
            data=request.data, context={'owner': user})
        serializer.is_valid(raise_exception=True)
        config = TerraformConfigService.create_from_text(
            owner=user, **serializer.validated_data)
        return self.success_response(
            TerraformConfigDetailSerializer(config).data, status=status.HTTP_201_CREATED)


# ── TerraformConfig (config-scoped) ────────────────────────────────────────────

class TerraformConfigDetail(APIView, ResponseMixin):
    def get(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        return self.success_response(TerraformConfigDetailSerializer(config).data)

    def put(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        serializer = TerraformConfigUpdateSerializer(
            data=request.data, context={'owner': config.owner, 'instance': config})
        serializer.is_valid(raise_exception=True)
        config = TerraformConfigService.update_config(
            config, **serializer.validated_data)
        return self.success_response(TerraformConfigDetailSerializer(config).data)

    def delete(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        TerraformConfigService.delete_config(config)
        return self.success_response({'message': 'Config deleted'})


class TerraformConfigContent(APIView, ResponseMixin):
    def get(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        content = TerraformConfigService.read_content(config)
        return self.success_response({'content': content})


class TerraformConfigFullScan(APIView, ResponseMixin):
    def post(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        ScanService.run_full_scan(config)
        report = ScanReportService.get_report_by_config(config)
        return self.success_response(ScanReportDetailSerializer(report).data)


class TerraformConfigManualScan(APIView, ResponseMixin):
    def post(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        serializer = ScanTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ScanService.run_manual_scan(
            config, serializer.validated_data['tool_ids'])
        report = ScanReportService.get_report_by_config(config)
        return self.success_response(ScanReportDetailSerializer(report).data)


class ScanReportDetail(APIView, ResponseMixin):
    def get(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        report = ScanReportService.get_report_by_config(config)
        return self.success_response(ScanReportDetailSerializer(report).data)

    def delete(self, request: common.Request, config_pk: int):
        config = TerraformConfigService.get_config_by_id(config_pk)
        check_owner(request, config.owner.pk)
        ScanReportService.delete_report(config)
        return self.success_response({'message': 'Report deleted'})


# ── TerraformTool (global) ─────────────────────────────────────────────────────

class TerraformToolList(APIView, ResponseMixin):
    def get(self, request: common.Request):
        tools = TerraformToolService.get_enabled_tools()
        return self.success_response(TerraformToolSerializer(tools, many=True).data)


# ── Report HTML / PDF (token via query param for browser navigation) ────────────

def _user_from_query_token(request):
    """Authenticate via ?token= query param. Returns User or None."""
    from kcore.models import User
    token_str = request.GET.get('token', '')
    if not token_str:
        return None
    try:
        data = AccessToken(token_str)
        return User.objects.get(pk=data['user_id'])
    except (TokenError, User.DoesNotExist, KeyError):
        return None


class ScanReportHTMLView(View):
    def get(self, request, config_pk: int):
        user = _user_from_query_token(request)
        if user is None:
            return HttpResponseForbidden('Invalid or missing token')

        try:
            config = TerraformConfigService.get_config_by_id(config_pk)
        except Exception:
            return HttpResponseNotFound('Config not found')
        if config.owner.pk != user.pk:
            return HttpResponseForbidden('Forbidden')

        try:
            report = ScanReportService.get_report_by_config(config)
        except Exception:
            return HttpResponseNotFound('No scan report for this config')

        html = _render_report_html(config, report)
        return HttpResponse(html, content_type='text/html; charset=utf-8')


class ScanReportPDFView(View):
    def get(self, request, config_pk: int):
        user = _user_from_query_token(request)
        if user is None:
            return HttpResponseForbidden('Invalid or missing token')

        try:
            config = TerraformConfigService.get_config_by_id(config_pk)
        except Exception:
            return HttpResponseNotFound('Config not found')
        if config.owner.pk != user.pk:
            return HttpResponseForbidden('Forbidden')

        try:
            report = ScanReportService.get_report_by_config(config)
        except Exception:
            return HttpResponseNotFound('No scan report for this config')

        pdf_bytes = _render_report_pdf(config, report)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="report_{config.name}.pdf"'
        return response


# ── Report rendering helpers ───────────────────────────────────────────────────

def _render_report_html(config, report) -> str:
    summary = report.result.get('summary', {})
    tools_data = report.result.get('tools', {})
    scanned_at = report.scanned_at.strftime('%Y-%m-%d %H:%M:%S UTC') if report.scanned_at else 'N/A'

    tool_names = ', '.join(t.name for t in report.tools.all()) or 'N/A'

    findings_html = ''
    for tool_name, tool_result in tools_data.items():
        items = tool_result.get('items', [])
        rows = ''.join(
            f'<tr>'
            f'<td>{i["rule_id"]}</td>'
            f'<td style="color:{"#c0392b" if i["severity"]=="HIGH" else "#e67e22" if i["severity"]=="MEDIUM" else "#27ae60"}">'
            f'{i["severity"]}</td>'
            f'<td>{i["description"]}</td>'
            f'<td>{i["location"]}</td>'
            f'</tr>'
            for i in items
        ) or '<tr><td colspan="4" style="color:green">No findings</td></tr>'
        findings_html += f'''
        <h3>{tool_name}</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
          <thead style="background:#f0f0f0">
            <tr><th>Rule ID</th><th>Severity</th><th>Description</th><th>Location</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>'''

    return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Scan Report — {config.name}</title>
  <style>
    body {{ font-family: monospace; padding: 32px; max-width: 960px; margin: auto; }}
    table {{ font-size: 13px; }}
    th, td {{ text-align: left; padding: 6px 10px; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:12px; }}
  </style>
</head>
<body>
  <h1>Scan Report</h1>
  <p><b>Config:</b> {config.name}</p>
  <p><b>Scanned at:</b> {scanned_at}</p>
  <p><b>Tools:</b> {tool_names}</p>
  <p><b>Status:</b> {report.status}</p>
  <h2>Summary</h2>
  <p>
    <span style="color:#c0392b">HIGH: {summary.get("high", 0)}</span> &nbsp;
    <span style="color:#e67e22">MEDIUM: {summary.get("medium", 0)}</span> &nbsp;
    <span style="color:#27ae60">LOW: {summary.get("low", 0)}</span>
  </p>
  <h2>Findings</h2>
  {findings_html or '<p>No findings data.</p>'}
</body>
</html>'''


def _render_report_pdf(config, report) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story = []

    summary = report.result.get('summary', {})
    tools_data = report.result.get('tools', {})
    scanned_at = report.scanned_at.strftime('%Y-%m-%d %H:%M:%S UTC') if report.scanned_at else 'N/A'
    tool_names = ', '.join(t.name for t in report.tools.all()) or 'N/A'

    story.append(Paragraph(f'Scan Report — {config.name}', styles['Title']))
    story.append(Spacer(1, 4*mm))
    for label, value in [('Config', config.name), ('Scanned at', scanned_at),
                         ('Tools', tool_names), ('Status', report.status)]:
        story.append(Paragraph(f'<b>{label}:</b> {value}', styles['Normal']))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph('Summary', styles['Heading2']))
    summary_data = [['HIGH', 'MEDIUM', 'LOW'],
                    [str(summary.get('high', 0)),
                     str(summary.get('medium', 0)),
                     str(summary.get('low', 0))]]
    t = Table(summary_data, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (0, 1), colors.red),
        ('TEXTCOLOR', (1, 1), (1, 1), colors.orange),
        ('TEXTCOLOR', (2, 1), (2, 1), colors.green),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    cell_style = ParagraphStyle('cell', fontSize=8, leading=10)
    hdr_style  = ParagraphStyle('hdr',  fontSize=8, leading=10, fontName='Helvetica-Bold')

    def sev_color(sev: str):
        s = sev.upper()
        if s in ('HIGH', 'CRITICAL'):
            return colors.red
        if s == 'MEDIUM':
            return colors.orange
        return colors.green

    story.append(Paragraph('Findings', styles['Heading2']))
    for tool_name, tool_result in tools_data.items():
        story.append(Paragraph(tool_name, styles['Heading3']))
        items = tool_result.get('items', [])
        if not items:
            story.append(Paragraph('No findings.', styles['Normal']))
        else:
            rows = [[
                Paragraph('Rule ID', hdr_style),
                Paragraph('Severity', hdr_style),
                Paragraph('Description', hdr_style),
                Paragraph('Location', hdr_style),
            ]]
            for item in items:
                sev = item.get('severity', '')
                sev_style = ParagraphStyle('sev', fontSize=8, leading=10, textColor=sev_color(sev))
                rows.append([
                    Paragraph(item.get('rule_id', ''), cell_style),
                    Paragraph(sev, sev_style),
                    Paragraph(item.get('description', ''), cell_style),
                    Paragraph(item.get('location', ''), cell_style),
                ])
            # A4 content width = 210 - 40 = 170mm
            ft = Table(rows, colWidths=[50*mm, 20*mm, 70*mm, 30*mm])
            ft.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(ft)
        story.append(Spacer(1, 4*mm))

    doc.build(story)
    return buf.getvalue()
