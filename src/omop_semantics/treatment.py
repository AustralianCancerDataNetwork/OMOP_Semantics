from .base import ConceptEnum

class Modality(ConceptEnum):
    chemotherapy = 35803401
    radiotherapy = 35803411

class TreatmentIntent(ConceptEnum):
    neoadjuvant = 4161587
    adjuvant = 4191637
    curative = 4162591
    palliative = 4179711

class CancerProcedureTypes(ConceptEnum):
    surgical_procedure = 4301351
    historical_procedure = 1340204
    rt_procedure = 1242725            # Radiotherapy procedure parent
    rn_procedure = 4161415            # Radionuclide parent
    rt_externalbeam = 4141448         # ebrt parent
    rt_course = 37163499              # overall RT course as a procedure - used to hold intent modifier, as well as to compare intended vs. delivered treatment events

class CancerConsultTypes(ConceptEnum):
    medonc = 4147722
    clinonc = 4139715 # there is no suitable radonc code? only radiotherapist?

class ProceduresByLocation(ConceptEnum):
    procedure_on_lung = 4040549
    operation_on_lung = 4301352