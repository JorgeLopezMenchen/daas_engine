import numpy as np

class KalmanRegimeFilter:
    """
    Filtro de Kalman Cinemático para DaaS B2B.
    Asume un modelo de movimiento uniformemente acelerado de Newton.
    Extrae la señal subyacente (Precio verdadero, Vel, Acel) del ruido del exchange.
    """
    def __init__(self, delta_t=1.0, process_noise=1e-4, measurement_noise=1e-2):
        # dt = Paso temporal (e.g., 1 vela)
        dt = delta_t
        
        # 1. Vector de estado inicial [x]: [Precio, Velocidad, Aceleración]
        self.x = np.zeros(3)
        
        # 2. Matriz de Transición de Estado [F] (Ecuaciones de Newton)
        # x_k = x_{k-1} + v*dt + 0.5*a*dt^2
        # v_k = v_{k-1} + a*dt
        # a_k = a_{k-1}
        self.F = np.array([
            [1, dt, 0.5 * dt**2],
            [0,  1, dt         ],
            [0,  0, 1          ]
        ])
        
        # 3. Matriz de Observación [H] (Solo podemos observar el precio, no la vel ni acel)
        self.H = np.array([[1, 0, 0]])
        
        # 4. Matriz de Covarianza del Error [P] (Nuestra incertidumbre inicial)
        self.P = np.eye(3) * 1.0
        
        # 5. Matriz de Covarianza del Ruido del Proceso [Q] (Flexibilidad del modelo)
        self.Q = np.eye(3) * process_noise
        
        # 6. Matriz de Covarianza del Ruido de la Medida [R] (Incertidumbre del Exchange)
        self.R = np.array([[measurement_noise]])
        
        self.is_initialized = False

    def update(self, observed_price: float) -> tuple:
        """
        Ejecuta el ciclo de Predicción/Corrección en tiempo O(1).
        Devuelve: (precio_filtrado, velocidad, aceleracion)
        """
        if not self.is_initialized:
            # En el primer tick, calibramos el radar a la posición inicial
            self.x[0] = observed_price
            self.is_initialized = True
            return (self.x[0], self.x[1], self.x[2])

        # --- FASE 1: PREDICCIÓN (A priori) ---
        # Dónde creemos que está el precio basado en la física
        x_pred = np.dot(self.F, self.x)
        # Cómo crece la incertidumbre de nuestra predicción
        P_pred = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q

        # --- FASE 2: CORRECCIÓN (A posteriori) ---
        # Innovación (y): La diferencia entre el precio real de Alpaca y nuestra predicción
        y = observed_price - np.dot(self.H, x_pred)
        
        # Varianza de la Innovación (S)
        S = np.dot(np.dot(self.H, P_pred), self.H.T) + self.R
        
        # Ganancia de Kalman (K): La "magia". Decide si fiarse más del Exchange o de la Matemática.
        K = np.dot(np.dot(P_pred, self.H.T), np.linalg.inv(S))
        
        # Actualizamos el estado real de la matriz
        self.x = x_pred + np.dot(K, y).flatten()
        
        # Actualizamos la confianza de nuestra matriz de error
        I = np.eye(self.P.shape[0])
        self.P = np.dot((I - np.dot(K, self.H)), P_pred)
        
        return (self.x[0], self.x[1], self.x[2])