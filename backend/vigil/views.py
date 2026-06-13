from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import common

from common.response import ResponseMixin
from .serializers import FlowInputSerializer, BatchFlowInputSerializer, DetectionRecordSerializer
from .models import DetectionRecord
from . import services



class DetectView(APIView, ResponseMixin):
    """POST /api/vigil/detect/ — run a single flow through all (or one) model."""

    def post(self, request: common.Request):
        s = FlowInputSerializer(data=request.data)
        if not s.is_valid():
            return self.bad_request_response(str(s.errors))
        try:
            results = services.detect_flow(s.validated_data)
        except KeyError as e:
            return self.bad_request_response(str(e))
        return self.success_response({"results": results, "count": len(results)})


class DetectBatchView(APIView, ResponseMixin):
    """POST /api/vigil/detect/batch/ — run multiple flows."""

    def post(self, request: common.Request):
        s = BatchFlowInputSerializer(data=request.data)
        if not s.is_valid():
            return self.bad_request_response(str(s.errors))
        try:
            results = services.detect_batch(
                s.validated_data["flows"],
                model_name=s.validated_data.get("model"),
            )
        except KeyError as e:
            return self.bad_request_response(str(e))
        return self.success_response({"results": results, "count": len(results)})


class RecordsView(APIView, ResponseMixin):
    """GET /api/vigil/records/ — paginated detection history."""

    def get(self, request: common.Request):
        only_attacks = request.query_params.get("only_attacks", "false").lower() == "true"
        model_name = request.query_params.get("model_name")
        limit = min(int(request.query_params.get("limit", 50)), 500)
        offset = int(request.query_params.get("offset", 0))

        qs = DetectionRecord.objects.all()
        if only_attacks:
            qs = qs.filter(is_attack=True)
        if model_name:
            qs = qs.filter(model_name=model_name)
        records = qs[offset: offset + limit]
        return self.success_response({
            "records": DetectionRecordSerializer(records, many=True).data,
            "count": len(records),
        })


class RecordDetailView(APIView, ResponseMixin):
    """GET /api/vigil/records/<id>/ — full detail of one detection record."""

    def get(self, request: common.Request, pk: int):
        try:
            record = DetectionRecord.objects.get(pk=pk)
        except DetectionRecord.DoesNotExist:
            return self.error_response("not found", status_code=404)
        return self.success_response(DetectionRecordSerializer(record).data)


class StatsView(APIView, ResponseMixin):
    """GET /api/vigil/stats/ — dashboard summary."""

    def get(self, request: common.Request):
        return self.success_response(services.get_stats())


class ModelsView(APIView, ResponseMixin):
    """GET /api/vigil/models/ — list registered models."""

    def get(self, request: common.Request):
        return self.success_response({"models": services.list_models()})

