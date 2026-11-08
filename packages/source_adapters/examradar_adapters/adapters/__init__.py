from ..base import Adapter
from .ibps import IBPS
from .kdrb import KDRB
from .kerala_psc import KeralaPSC
from .nta import NTA
from .rbi import RBI
from .rrb import RRB
from .sbi import SBI
from .ssc import SSC
from .upsc import UPSC

ADAPTERS: dict[str, type[Adapter]] = {
    a.key: a for a in (KeralaPSC, UPSC, SBI, IBPS, NTA, RRB, KDRB, RBI, SSC)
}
