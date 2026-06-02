#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 19 11:35:23 2021

@author: inti
"""
#Funciones para determinar el omega que maximiza la medida de GTI (ajustada)
import pandas as pd
import numpy as np
import pvlib as pv
from fun import modelado as md
from fun import indicadores

def getIntervalGTImax(GTI,deltaT=1): 
    #Devuelve la GTI alrededor del máximo (+- 1h por def)
    t_max = GTI.idxmax()
    t1 = t_max - pd.Timedelta(hours=deltaT)
    t2 = t_max + pd.Timedelta(hours=deltaT)
    return GTI.loc[t1:t2], t1, t2

def ajusteGTI(GTImax_intervalo,grado=4):
    #Devuelve la GTI ajustada por un pol. de gr 4 
    x_val = np.linspace(0,1,len(GTImax_intervalo))
    y_val = GTImax_intervalo
    
    coeffs = np.polyfit(x_val,y_val,grado)
    poly_eqn = np.poly1d(coeffs)
    y_hat = pd.Series(poly_eqn(x_val),index=GTImax_intervalo.index)
    
    return y_hat

def getDeltaOmega(GTI_ajustada,omegaDeg):
    tmax = GTI_ajustada.idxmax()
    dw = omegaDeg[tmax]
    
    return dw

#Funciones para calcular la curva característica omega vs gamma.
def getTL(ciclosTL,est,doy):
    TL = ciclosTL[est]
    doy_medio = [15, 45, 75, 105, 136, 166, 197, 228, 258, 289, 319, 350] #doy del centro de cada mes
    TLinterp = np.interp(doy , doy_medio, TL, period = 366)
    
    return TLinterp
    

def getGTIcsk(BETAdeg,az,Zdeg,gammaDeg,Go,alturaSolar,Zsnm,TL=2.5):
    
    GHIesra,DHIesra,DNIesra = md.generaComponentesESRA(alturaSolar,Go,Zsnm,TL=TL)
    GTIesra = (pv.irradiance.get_total_irradiance(BETAdeg, az, Zdeg, gammaDeg, 
                                             DNIesra, GHIesra, DHIesra,Go, albedo=0.25))
    GTIesra = GTIesra['poa_global']
    
    return GTIesra


def getSerieTempAux(datos):
    #Creo una serie temporal con resulución de segundos, para el día de esos datos
    serieTemp_1s = datos.asfreq('1s').index
    return serieTemp_1s

def calculosSolares(loc,serieTemp_1s):
    #Calculo el df solar_pos que guarda información de los ángulos solares
    solar_pos_1s = loc.get_solarposition(serieTemp_1s)
    
    return solar_pos_1s

def curvaCaracteristica(loc,solar_pos_1s,BETAdeg,Zsnm,TL,azimuts):
    ''' Calcula las delta omega para el rango dado por (-az_lim,az_lim). Devuelve
    el rango de azimuts y las delta omega correspondientes
    '''
    #Extraigo/calculo las variables solares relevantes:
    Zdeg = solar_pos_1s['zenith']
    gammaDeg = solar_pos_1s['azimuth']
    alturaSolar = solar_pos_1s['elevation']
    omegaDeg = pv.solarposition.hour_angle(solar_pos_1s.index, loc.longitude, solar_pos_1s.equation_of_time)
    omegaDeg = pd.Series(omegaDeg,index = solar_pos_1s.index)
    Go = pv.irradiance.get_extra_radiation(solar_pos_1s.index)
  
    #Recorre el rango de azimuts, calcula GTIesra y determina el omega que maximiza GTIesra
    #azimuts = range(-az_lim,az_lim)
    dw_azimutal = np.zeros(len(azimuts))
    j = 0
    for az_deg in azimuts:
        GTIaux = getGTIcsk(BETAdeg,az_deg,Zdeg,gammaDeg,Go,alturaSolar,Zsnm,TL)
        dw_azimutal[j] = omegaDeg.loc[GTIaux.idxmax()]
        j += 1
        
    
    return dw_azimutal

# def ajustaCurva(azimuts,dw_azimutal):
#     '''Ajusta la curva delta omega en función del azimut por un polinomio de 3º grado, devolviendo los valores
#     funcionales del ajuste así como la ecuación del mismo.
#     '''
#     x_val = azimuts; y_val = dw_azimutal
#     coeffs = np.polyfit(x_val,y_val,3)
#     poly_eqn = np.poly1d(coeffs)
#     y_hat = poly_eqn(x_val)
    
#     return y_hat, poly_eqn

def ajustaCurva(dw_azimutal,azimuts):
    '''Ajusta la curva delta omega en función del azimut por un polinomio de 3º grado, devolviendo los valores
    funcionales del ajuste así como la ecuación del mismo.
    '''
    x_val = dw_azimutal; y_val = -azimuts
    coeffs = np.polyfit(x_val,y_val,3)
    poly_eqn = np.poly1d(coeffs)
    y_hat = poly_eqn(x_val)
    
    return y_hat, poly_eqn

# def interpola(dwExperimental,poly_eqn,azimuts):
#     '''Recibe un delta omega obtenido experimentalmente y el resultado del ajuste de la curva, interpola
#     y devuelve el resultado, que corresponde a la estimación del azimut (dado que es el corte de una recta
#     con un polinomio de 3º grado, son 3 soluciones y hay que elegir la que está en el intervalo (-az,az))
#     '''
#     raices = np.roots(poly_eqn - dwExperimental)
#     raiz = raices[(raices<azimuts[-1])&(raices>(azimuts[0]))]
    
#     if len(raiz) == 0:
#         print('No encuentra solución!')
#         raiz = np.nan
#     elif len(raiz) == 1:
#         raiz = -np.real(raiz[0])
#     else:
#         print('Mas de una solución, revisar')
#         raiz = np.nan 
        
#     return raiz

def interpola(dwExperimental,poly_eqn):
    '''Evalúa el w* en el polinomio que sale del ajuste gamma = f(w)
        obteniendo el valor de azimut 
     '''
    gamma = np.polyval(poly_eqn, dwExperimental)
 
    return gamma

#Funciones misceláneas:
def preparaDatos(rutaPX,year,PX,est,doy,tz):
    if (est=='TT') | (est=='TA'):
        fileName = rutaPX + '{0}/PX{1:0=2d}_{2}_RAD_{3}{4:0=3d}.csv'.format(year,PX,est,year,doy)
    elif est=='AR':
        fileName = rutaPX + '{0}/PX{1:0=2d}_{2}c_{3}{4:0=3d}.csv'.format(year,PX,est,year,doy)
    datos = pd.read_csv(fileName, index_col = 'Fecha')
    datos.index = pd.to_datetime(datos.index)
    datos.index = datos.index.tz_localize(tz)
    
    datos = datos[['GHI1','GTI']] #me quedo  con las columnas relevantes
    
    return datos

def getVariablesSolares(solar_pos,loc):
    Zdeg = solar_pos['zenith']
    gammaDeg = solar_pos['azimuth']
    alturaSolar = solar_pos['elevation']
    omegaDeg = pv.solarposition.hour_angle(solar_pos.index, loc.longitude, solar_pos.equation_of_time)
    omegaDeg = pd.Series(omegaDeg,index = solar_pos.index)
    Go = pv.irradiance.get_extra_radiation(solar_pos.index)
    
    return Zdeg, gammaDeg, alturaSolar, omegaDeg, Go

#%% Funciones para el segundo método de detección de azimut (mínimo de indicadores del pasaje a PI con azimut variable)

def getAZmetodo2(BETAdeg,zenith,azimutSolar,DNI,GHI,DHI,GTI,AM,Go,azimuts,mskFINAL,albedo=0.2, model='isotropic'):
    rms = np.zeros(len(azimuts))
    i = 0
    for gamma in azimuts:
        GTIm = (pv.irradiance.get_total_irradiance(BETAdeg,gamma,zenith[mskFINAL],azimutSolar[mskFINAL],
                                        DNI[mskFINAL],GHI[mskFINAL],DHI[mskFINAL],Go[mskFINAL],AM[mskFINAL],albedo=albedo,model=model))
        GTIm = GTIm['poa_global']
        GTImedia,_,RMSD,rMBE,rRMSD = indicadores.desvios(GTIm[mskFINAL], GTI[mskFINAL])
            
        
        rms[i] = rRMSD
        #rms[i] = RMSD
        
        i = i + 1
    
    AZ = azimuts[rms==rms.min()][0]
    
    return AZ, rms

#%% Funciones para el método analítico de detección de azimut 

def omega_ast(GTIdato,omegaDeg,exp=3,dt=1,deg=2):
    """ input:  - exp (exponente de la GTIdato a ajustar)
                - dt (intervalo en horas del ajuste alrededor del mediodía)
                - deg (grado del ajuste de GTI^exp)
        output: - w_ast (w*)
                - t_ast (t*)
                - GTI_ajustada (ajuste de GTI^exp alrededor del mediodía solar de la sup.)
                - GTI_intervalo (dato de GTI alrededor del mediodía de la superifcie)
                
    """
    GTI_intervalo,_,_ = getIntervalGTImax(GTIdato,deltaT=dt)
    GTI_ajustada = ajusteGTI(GTI_intervalo**exp,grado=2)
    
    t_ast = GTI_ajustada.idxmax()
    w_ast = omegaDeg[t_ast]
    
    return w_ast, t_ast, GTI_ajustada, GTI_intervalo
    
def get_mkr(cosz):
    m = 1/cosz
    P4 = (6.62960 + 1.75130*m - 0.12020*(m**2) + 0.00650*(m**3) - 0.00013*(m**4))
    mkr = m/P4

    return mkr


def ajusteAB(cosw,cosz):
    coeffs = np.polyfit(cosw,cosz,1)
    A = coeffs[1]; B = coeffs[0]
    
    return A,B

# def func(azimuth,sinDelta,cosDelta,):
    
    
def eqn(x,DOY,LATdeg,BETAdeg,w_ast,m,d_mkr_ast,TL,A,B,xi,fd):
    

    
    sinDelta = np.sin(pv.solarposition.declination_spencer71(DOY))
    cosDelta = np.cos(pv.solarposition.declination_spencer71(DOY))
    sinPhi = np.sin(np.deg2rad(LATdeg)); cosPhi = np.cos(np.deg2rad(LATdeg))
    sinBeta = np.sin(np.deg2rad(BETAdeg)); cosBeta = np.cos(np.deg2rad(BETAdeg))
    sinw = np.sin(np.deg2rad(w_ast)); cosw = np.cos(np.deg2rad(w_ast))
    cosz = A + B*cosw
    m = 1/cosz

    
    a0 = sinDelta*sinPhi*cosBeta + sinDelta*cosPhi*sinBeta*np.cos(x)
    a1 = cosDelta*cosPhi*cosBeta - cosDelta*sinPhi*sinBeta*np.cos(x)
    a2 = cosDelta*sinBeta*np.sin(x)
    
    costheta = a0 + a1*cosw + a2*sinw 
    dcostheta = -a1*sinw + a2*cosw
    
    rb = costheta/cosz 
    rb_punto = m*(dcostheta - m*costheta*(-B*sinw))
    
    ec = rb_punto - (TL*d_mkr_ast + ((B*sinw) / (A + B*cosw))) * (rb + (xi/(1-fd))) 


    return ec


