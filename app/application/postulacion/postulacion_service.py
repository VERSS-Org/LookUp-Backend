"""
Servicio de Postulación - Enriquecimiento de datos
Agrega información relacionada a las postulaciones (candidato, puesto, empresa)
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from app.infrastructure.postulacion.repositories import PostulacionRepositoryImpl
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.infrastructure.iam.repositories import CuentaRepositoryImpl

# Importar tipos de dominio para reconocer aggregates
from app.domain.iam.entities import CuentaAggregate as CuentaAggregateDomain
from app.domain.puesto.entities import PuestoAggregate as PuestoAggregateDomain
from app.domain.iam.entities import Cuenta as CuentaEntity
from app.domain.puesto.entities import Puesto as PuestoEntity


class PostulacionService:
    """Servicio que enriquece datos de postulaciones con información relacionada"""
    
    def __init__(self):
        self.postulacion_repo = PostulacionRepositoryImpl()
        self.puesto_repo = PuestoRepositoryImpl()
        self.cuenta_repo = CuentaRepositoryImpl()

    @staticmethod
    def _valor_publico(valor: Any) -> Any:
        return valor.value if hasattr(valor, "value") else valor
    
    def enriquecer_postulacion(
        self,
        postulacion_data: Dict[str, Any],
        incluir_candidato: bool = True,
        incluir_puesto: bool = True,
        incluir_empresa: bool = True
    ) -> Dict[str, Any]:
        """
        Enriquece una postulación individual con datos relacionados
        
        Args:
            postulacion_data: Datos básicos de la postulación
            incluir_candidato: Si debe incluir info del candidato
            incluir_puesto: Si debe incluir info del puesto
            incluir_empresa: Si debe incluir info de la empresa
            
        Returns:
            Postulación enriquecida con datos relacionados
        """
        postulacion_enriquecida = postulacion_data.copy()
        
        try:
            # Obtener información del candidato
            if incluir_candidato and "candidato_id" in postulacion_data:
                candidato_info = self._obtener_info_candidato(
                    UUID(postulacion_data["candidato_id"])
                )
                if candidato_info:
                    postulacion_enriquecida["candidato"] = candidato_info
            
            # Obtener información del puesto
            if incluir_puesto and "puesto_id" in postulacion_data:
                puesto_info = self._obtener_info_puesto(
                    UUID(postulacion_data["puesto_id"])
                )
                if puesto_info:
                    postulacion_enriquecida["puesto"] = puesto_info

                    empresa_id = puesto_info.get("empresa_id")
                    if incluir_empresa and empresa_id:
                        empresa_info = self._obtener_info_empresa(UUID(empresa_id))
                        if empresa_info:
                            postulacion_enriquecida["empresa"] = empresa_info
        
        except Exception as e:
            # Log del error pero no fallar - devolver datos básicos
            print(f"Error enriqueciendo postulación: {str(e)}")
        
        return postulacion_enriquecida
    
    def enriquecer_postulaciones(
        self,
        postulaciones: List[Dict[str, Any]],
        incluir_candidato: bool = True,
        incluir_puesto: bool = True,
        incluir_empresa: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Enriquece múltiples postulaciones con datos relacionados
        
        Args:
            postulaciones: Lista de postulaciones básicas
            incluir_candidato: Si debe incluir info del candidato
            incluir_puesto: Si debe incluir info del puesto
            incluir_empresa: Si debe incluir info de la empresa
            
        Returns:
            Lista de postulaciones enriquecidas
        """
        return [
            self.enriquecer_postulacion(
                post,
                incluir_candidato=incluir_candidato,
                incluir_puesto=incluir_puesto,
                incluir_empresa=incluir_empresa
            )
            for post in postulaciones
        ]
    
    def _obtener_info_candidato(self, candidato_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene información básica del candidato"""
        try:
            cuenta = self.cuenta_repo.obtener_por_id(candidato_id)
            if not cuenta:
                return None

            # Manejar CuentaAggregate -> extraer entidad Cuenta
            # La implementación del repo devuelve un CuentaAggregate con atributo `cuenta`
            if hasattr(cuenta, "cuenta"):
                cuenta_obj = getattr(cuenta, "cuenta")
                nombre = getattr(cuenta_obj, "nombre_completo", "")
                email = getattr(getattr(cuenta_obj, "credencial", {}), "email", "")
                carrera = getattr(cuenta_obj, "carrera", None)
                telefono = getattr(cuenta_obj, "telefono", None)
                ciudad = getattr(cuenta_obj, "ciudad", None)
            elif isinstance(cuenta, dict):
                nombre = cuenta.get("nombre_completo", "")
                email = cuenta.get("email", "")
                carrera = cuenta.get("carrera")
                telefono = cuenta.get("telefono")
                ciudad = cuenta.get("ciudad")
            else:
                # Otros tipos: intentar acceder por atributos comunes
                nombre = getattr(cuenta, "nombre_completo", "")
                email = getattr(cuenta, "email", getattr(getattr(cuenta, "credencial", {}), "email", ""))
                carrera = getattr(cuenta, "carrera", None)
                telefono = getattr(cuenta, "telefono", None)
                ciudad = getattr(cuenta, "ciudad", None)

            return {
                "cuenta_id": str(candidato_id),
                "nombre_completo": nombre,
                "email": email,
                "carrera": carrera,
                "telefono": telefono,
                "ciudad": ciudad
            }
        except Exception as e:
            print(f"Error obteniendo candidato {candidato_id}: {str(e)}")
        
        return None
    
    def _obtener_info_puesto(self, puesto_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene información básica del puesto"""
        try:
            puesto = self.puesto_repo.obtener_por_id(puesto_id)
            if not puesto:
                return None

            # Si el repo devuelve un PuestoAggregate con atributo `puesto`
            if hasattr(puesto, "puesto"):
                puesto_obj = getattr(puesto, "puesto")
                titulo = getattr(puesto_obj, "titulo", "")
                descripcion = getattr(puesto_obj, "descripcion", "")
                ubicacion = getattr(puesto_obj, "ubicacion", "")
                salario_min = getattr(puesto_obj, "salario_min", None)
                salario_max = getattr(puesto_obj, "salario_max", None)
                moneda = getattr(puesto_obj, "moneda", "MXN")
                tipo_contrato = self._valor_publico(getattr(puesto_obj, "tipo_contrato", ""))
                empresa_id = getattr(puesto_obj, "empresa_id", None)
            elif isinstance(puesto, dict):
                titulo = puesto.get("titulo", "")
                descripcion = puesto.get("descripcion", "")
                ubicacion = puesto.get("ubicacion", "")
                salario_min = puesto.get("salario_min")
                salario_max = puesto.get("salario_max")
                moneda = puesto.get("moneda", "MXN")
                tipo_contrato = self._valor_publico(puesto.get("tipo_contrato", ""))
                empresa_id = puesto.get("empresa_id")
            else:
                titulo = getattr(puesto, "titulo", "")
                descripcion = getattr(puesto, "descripcion", "")
                ubicacion = getattr(puesto, "ubicacion", "")
                salario_min = getattr(puesto, "salario_min", None)
                salario_max = getattr(puesto, "salario_max", None)
                moneda = getattr(puesto, "moneda", "MXN")
                tipo_contrato = self._valor_publico(getattr(puesto, "tipo_contrato", ""))
                empresa_id = getattr(puesto, "empresa_id", None)

            empresa_id_str = str(empresa_id) if empresa_id is not None else ""

            return {
                "puesto_id": str(puesto_id),
                "titulo": titulo,
                "descripcion": descripcion,
                "ubicacion": ubicacion,
                "salario_min": salario_min,
                "salario_max": salario_max,
                "moneda": moneda,
                "tipo_contrato": str(tipo_contrato) if tipo_contrato is not None else "",
                "empresa_id": empresa_id_str
            }
        except Exception as e:
            print(f"Error obteniendo puesto {puesto_id}: {str(e)}")
        
        return None
    
    def _obtener_info_empresa(self, empresa_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene información básica de la empresa"""
        try:
            empresa = self.cuenta_repo.obtener_por_id(empresa_id)
            if not empresa:
                return None

            if hasattr(empresa, "cuenta"):
                empresa_obj = getattr(empresa, "cuenta")
                nombre = getattr(empresa_obj, "nombre_completo", "")
                email = getattr(getattr(empresa_obj, "credencial", {}), "email", "")
            elif isinstance(empresa, dict):
                nombre = empresa.get("nombre_completo", "")
                email = empresa.get("email", "")
            else:
                nombre = getattr(empresa, "nombre_completo", "")
                email = getattr(empresa, "email", "")

            return {
                "empresa_id": str(empresa_id),
                "nombre": nombre,
                "email": email
            }
        except Exception as e:
            print(f"Error obteniendo empresa {empresa_id}: {str(e)}")
        
        return None
