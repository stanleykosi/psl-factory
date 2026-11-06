"""Local transactional Finance inbox/report adapter. No external transport claimed."""
from apps.identity.services import require
from apps.core.models import Case
from apps.finance.recognition_models import ProgressPacket
class LocalRecognitionInbox:
 def read(self,actor,case_id):
  case=Case.objects.get(pk=case_id)
  for action in ['case.read','recognition.read','recognition.receive']:require(actor,case,action)
  return ProgressPacket.objects.filter(case=case,records__kind='request').distinct().order_by('-pk')
 def report(self,actor,packet_id):
  from apps.finance.recognition import position
  p=ProgressPacket.objects.get(pk=packet_id)
  for action in ['case.read','recognition.read','recognition.export']:require(actor,p.case,action)
  return position(p)
