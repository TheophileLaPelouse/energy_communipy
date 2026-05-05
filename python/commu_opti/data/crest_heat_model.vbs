' ===============================================================================================
' ## Low-order building thermal model
' ===============================================================================================


Option Explicit

' ===============================================================================================
' Class Variables

' // Index variables
Private intDwellingIndex As Integer
Private intRunNumber As Integer
Private intBuildingIndex As Integer
Private intHeatingSystemIndex As Integer

' // Low-order building thermal model parameters
' Thermal transfer coefficient between outside air and external building thermal capacitance (W/K)
Private dblH_ob As Double

' Thermal transfer coefficient between external building thermal capacitance and internal building thermal capacitance (W/K)
Private dblH_bi As Double

' Thermal transfer coefficient representing ventilation losses between outside air and internal building thermal capacitance (W/K)
Private dblH_v As Double

' Thermal transfer coefficient between inside building node and heating system emitters (W/K)
Private dblH_em As Double

' Thermal transfer coefficient between inside building node and cooling system emitters (W/K)
Private dblH_cool As Double

' thermal transfer coefficient between hot water tank and dwelling internal building node
Private dblH_loss As Double

' External building thermal capacitance (J/K)
Private dblC_b As Double

' Internal building thermal capacitance (J/K)
Private dblC_i As Double

' Thermal capacitance of heat emitters (J/K)
Private dblC_em As Double

' Thermal capacitance of cooler emitters (J/K)
Private dblC_cool As Double

' thermal capacitance of hot water cylinder
Private dblC_cyl As Double

' Global irradiance multiplier (m^2)
Private dblA_s As Double

' temperature of cold water inlet
Private dblTheta_cw As Double

' External temperature for initialisation of building temperatures
Private dblTheta_o As Double

' // Arrays to store building temperature variables (dependent variables)

' Temperature of external building node
Private aTheta_b(1 To 1440, 1 To 1) As Double

' Temperature of internal building node
Private aTheta_i(1 To 1440, 1 To 1) As Double

' Temperature of heat emitters
Private aTheta_em(1 To 1440, 1 To 1) As Double

' Temperature of cooler emitters
Private aTheta_cool(1 To 1440, 1 To 1) As Double

' array to store the variable thermal heat transfer coefficient associated with the hot water demand
Private aTheta_cyl(1 To 1440, 1 To 1) As Double

' Passive solar gains
Private aPhi_s(1 To 1440, 1 To 1) As Double

' Casual thermal gains
Private aPhi_c(1 To 1440, 1 To 1) As Double

' Number of second in the simulation's time step
Private intTimeStep As Integer
    

' ===============================================================================================
' Class Properties

' Routine to return internal building node temperature for a particular time step
Public Property Get GetTheta_i(timestep As Integer)
    GetTheta_i = aTheta_i(timestep, 1)
End Property

' Return the hot water cylinder temperature for a given time step
Public Property Get GetTheta_cyl(timestep As Integer)
    GetTheta_cyl = aTheta_cyl(timestep, 1)
End Property

' Routine to return heat emitter temperature for a given time step
Public Property Get GetTheta_em(timestep As Integer)
    GetTheta_em = aTheta_em(timestep, 1)
End Property

' Routine to return cooler emitter temperature for a given time step
Public Property Get GetTheta_cool(timestep As Integer)
    GetTheta_cool = aTheta_cool(timestep, 1)
End Property

Public Property Get GetMeanTheta_i() As Double
    GetMeanTheta_i = WorksheetFunction.Average(aTheta_i)
End Property

' Routine to return the target heat output required for hot water
Public Property Get GetPhi_hWater(timestep As Integer)
    Dim dblPhi_target As Double
    Dim dblTheta_target As Double
    Dim dblTheta_cyl As Double
    Dim dblH_dhw As Double
    Dim dblTheta_i As Double
    
    ' // Get the hot water thermostat set point for this dwelling
    dblTheta_target = aHeatingControls(intRunNumber).GetHotWaterThermostatSetpoint
    
    ' // Get the relevant building thermal node temperatures
    ' // If the first time step use initial conditions
    ' // otherwise use previous time step
    If timestep = 1 Then
        dblTheta_cyl = aTheta_cyl(timestep, 1)
        dblTheta_i = aTheta_i(timestep, 1)
    Else
        dblTheta_cyl = aTheta_cyl(timestep - 1, 1)
        dblTheta_i = aTheta_i(timestep - 1, 1)
    End If
    ' // Get the variable hot water demand heat transfer coefficient for this time step
    dblH_dhw = aHotWater(intRunNumber).GetH_demand(timestep)
    
    ' // Calculate target heat input required from heating system to deliver appropriate
    ' // temperature of hot water
    
    dblPhi_target = dblC_cyl / intTimeStep * (dblTheta_target - dblTheta_cyl) _
                        + dblH_dhw * (dblTheta_cyl - dblTheta_cw) _
                        + dblH_loss * (dblTheta_cyl - dblTheta_i)
    
    GetPhi_hWater = dblPhi_target
End Property

' Routine to return the target heat output for space heating
Public Property Get GetPhi_hSpace(timestep As Integer)
'wsMain.Range("M18") = " Started timestep: " + CStr(timestep)
    Dim dblPhi_hSpaceTarget As Double
    Dim dblTheta_i As Double
    Dim intOffset As Integer
    
    ' Temperature of the emitters in the previous time step
    Dim dblTheta_em As Double
    
    ' Temperature deadband for emitters
    Dim dblEmitterDeadband As Double
    
    ' Target temperature for the emitters
    Dim dblTheta_emTarget As Double
    
    intOffset = 4
    
    dblEmitterDeadband = 5
    
    dblTheta_emTarget = dblEmitterDeadband + Application.index(wsBuildings.Range("rTheta_em"), intOffset + intBuildingIndex).Value
    
    ' // Get the relevant building thermal node temperatures
    If timestep = 1 Then
        dblTheta_em = aTheta_em(timestep, 1)
        dblTheta_i = aTheta_i(timestep, 1)
    Else
        dblTheta_em = aTheta_em(timestep - 1, 1)
        dblTheta_i = aTheta_i(timestep - 1, 1)
    End If
    
    ' // calculate the target heat delivery to heat emitters to achieve the set point
    dblPhi_hSpaceTarget = dblC_em / intTimeStep * (dblTheta_emTarget - dblTheta_em) _
                            + dblH_em * (dblTheta_em - dblTheta_i)
                            
    GetPhi_hSpace = dblPhi_hSpaceTarget
'wsMain.Range("M18") = " Finished dblPhi_hSpaceTarget: " + CStr(dblPhi_hSpaceTarget)
End Property

' Routine to return the target cooling output for space cooling
Public Property Get GetPhi_hCooling(timestep As Integer)
'wsMain.Range("M18") = " Started timestep: " + CStr(timestep)
    Dim dblPhi_hCoolingTarget As Double
    Dim dblTheta_i As Double
    Dim intOffset As Integer
    
     ' Temperature of the emitters in the previous time step
    Dim dblTheta_cool As Double
    
    ' Temperature deadband for emitters
    Dim dblEmitterDeadband As Double
    
    ' Target temperature for the emitters
    Dim dblTheta_coolTarget As Double
       
    intOffset = 4
    
    dblEmitterDeadband = 5
    
    dblTheta_coolTarget = Application.index(wsBuildings.Range("rTheta_cool"), intOffset + intBuildingIndex).Value _
        - dblEmitterDeadband
        
    ' // Get the relevant building thermal node temperatures
    If timestep = 1 Then
        dblTheta_i = aTheta_i(timestep, 1)
    Else
        dblTheta_i = aTheta_i(timestep - 1, 1)
    End If
    
    ' // calculate the target heat delivery to room to achieve the set point
    dblPhi_hCoolingTarget = dblC_cool / intTimeStep * (dblTheta_coolTarget - dblTheta_cool) _
                            + dblH_cool * (dblTheta_cool - dblTheta_i)
                            
    GetPhi_hCooling = dblPhi_hCoolingTarget
'wsMain.Range("M18") = " Finished dblPhi_hSpaceTarget: " + CStr(dblPhi_hSpaceTarget)
End Property
' ===============================================================================================
' Class Subroutines

' ===============================================================================================
' ## InitialiseBuilding
' Initialise the building object for this dwelling
' ===============================================================================================
Public Sub InitialiseBuilding(dwellingIndex As Integer, runNumber As Integer)
    Dim intOffset As Integer
    
    ' DHW cylinder volume
    Dim dblV_cyl As Double
    
    intOffset = 4
    
    ' // get the simulation time step
    intTimeStep = 60 ' //(s)
    
    intDwellingIndex = dwellingIndex
    intRunNumber = runNumber
    With wsDwellings
        intBuildingIndex = Application.index(.Range("rBuildingIndex"), intDwellingIndex + intOffset).Value
        intHeatingSystemIndex = Application.index(.Range("rPrimaryHeatingIndex"), intOffset + intDwellingIndex).Value
    End With
    
    With wsBuildings
    
        ' // Get building thermal model parameters
        dblH_ob = Application.index(.Range("rH_ob"), intOffset + intBuildingIndex).Value
        dblH_bi = Application.index(.Range("rH_bi"), intOffset + intBuildingIndex).Value
        dblH_v = Application.index(.Range("rH_v"), intOffset + intBuildingIndex).Value
        dblC_b = Application.index(.Range("rC_b"), intOffset + intBuildingIndex).Value
        dblC_i = Application.index(.Range("rC_i"), intOffset + intBuildingIndex).Value
        dblA_s = Application.index(.Range("rA_s"), intOffset + intBuildingIndex).Value
        dblH_em = Application.index(.Range("rH_em"), intOffset + intBuildingIndex).Value
        dblC_em = Application.index(.Range("rC_em"), intOffset + intBuildingIndex).Value
        ' // Extra parameters added to represent the properties of the cooling system
        dblH_cool = Application.index(.Range("rH_emcool"), intOffset + intBuildingIndex).Value
        dblC_cool = Application.index(.Range("rC_emcool"), intOffset + intBuildingIndex).Value
                
    End With
    
    ' // Get hot water system parameters
    With wsPrimaryHeatingSystems
        
        ' // Get thermal resistance between hot water tank and internal building node
        dblH_loss = Application.index(.Range("rH_loss"), intOffset + intHeatingSystemIndex).Value
                
        ' // Calculate thermal capacity of hot water tank
        dblV_cyl = Application.index(.Range("rV_cyl"), intOffset + intHeatingSystemIndex).Value
        dblC_cyl = SPECIFIC_HEAT_CAPACITY_WATER * dblV_cyl
        
    End With
    
    ' // Assign initial building temperatures
    ' // In hot climates or warm weather the initial building temperatures are likely to
    ' // be increased external temperature
    dblTheta_o = aLocalClimate(intRunNumber).GetTheta_o(1)
    aTheta_b(1, 1) = Rnd * 2 + WorksheetFunction.Max(16, dblTheta_o)
    aTheta_i(1, 1) = Rnd * 2 + WorksheetFunction.Min(WorksheetFunction.Max(19, dblTheta_o), 25)
    aTheta_em(1, 1) = aTheta_i(1, 1)
    aTheta_cool(1, 1) = aTheta_i(1, 1)
    
    ' // Set the initial temperature of the hot water tank
    aTheta_cyl(1, 1) = 60 + Rnd() * 2

    ' // Set cold water inlet temperature
    dblTheta_cw = 10
    
End Sub




' ===============================================================================================
' ## CalculateTemperatureChange
'
' ===============================================================================================
Public Sub CalculateTemperatureChange(currentTimeStep As Integer)

    ' // Declare variables
    ' Temperature of outside air (degrees)
    Dim dblTheta_o As Double
    
    ' External building node temperature in previous time step
    Dim dblTheta_b As Double
    
    ' Internal building node temperature in previous time step
    Dim dblTheta_i As Double
    
    ' Emitter temperature in previous time step
    Dim dblTheta_em As Double
    
    ' Cooler Emitter temperature in previous time step
    Dim dblTheta_cool As Double
    
    ' temperature of hot water in tank (in previous time step)
    Dim dblTheta_cyl As Double
    
    ' change in external building node temperature in current time step
    Dim dblDeltaTheta_b As Double
    
    ' change in internal building node temperature in current time step
    Dim dblDeltaTheta_i As Double
    
    ' change in emitter node temperature in current time step
    Dim dblDeltaTheta_em As Double
    
    ' change in emitter node temperature in current time step
    Dim dblDeltaTheta_cool As Double
    
    ' change in temperature of hot water in tank
    Dim dblDeltaTheta_cyl As Double
    
    ' variable thermal transfer coefficient between hot water tank and cold water inlet
    ' temperature - represents hot water demand
    Dim dblH_dhw As Double
    
    ' External radiation (W/m^2)
    Dim dblG_o As Double
    
    ' Thermal gains from heating system to space (W)
    Dim dblPhi_hSpace As Double
    
    ' Thermal cooling from cooling system to space (W)
    Dim dblPhi_hCooling As Double
    
    ' Thermal gains from heatings system to hot water
    Dim dblPhi_hWater As Double
    
    ' Casual thermal gains from occupants, lighting, and appliances (W)
    Dim dblPhi_c As Double
    
    ' Casual thermal gains from occupants
    Dim dblPhi_cOccupancy As Double
    
    ' Casual thermal gains from lighting
    Dim dblPhi_cLighting As Double
    
    ' Casual thermal gains from appliances
    Dim dblPhi_cAppliances As Double
    
    ' Passive solar thermal gains (W)
    Dim dblPhi_s As Double
    
    ' Hot water cylinder gains from solar collector (if any)
    Dim dblPhi_collector As Double
    
    ' // Get the external temperature and irradiance values for this time step
    dblTheta_o = aLocalClimate(intRunNumber).GetTheta_o(currentTimeStep)
    dblG_o = aLocalClimate(intRunNumber).GetG_o(currentTimeStep)
    
    ' // If this is the first time step then get the initial conditions
    If currentTimeStep = 1 Then
        dblTheta_b = aTheta_b(currentTimeStep, 1)
        dblTheta_i = aTheta_i(currentTimeStep, 1)
        dblTheta_em = aTheta_em(currentTimeStep, 1)
        dblTheta_cool = aTheta_cool(currentTimeStep, 1)
        dblTheta_cyl = aTheta_cyl(1, 1)
    Else
        ' // Otherwise get the building temperatures for the previous time step
        dblTheta_b = aTheta_b(currentTimeStep - 1, 1)
        dblTheta_i = aTheta_i(currentTimeStep - 1, 1)
        dblTheta_em = aTheta_em(currentTimeStep - 1, 1)
        dblTheta_cool = aTheta_cool(currentTimeStep - 1, 1)
        dblTheta_cyl = aTheta_cyl(currentTimeStep - 1, 1)
    End If
    
    ' // Get or calculate the thermal gains
    
    ' //... from primary heating system to space
    dblPhi_hSpace = aPrimaryHeatingSystem(intRunNumber).GetHeatToSpace(currentTimeStep)
    
    ' //... from cooling system to space
    dblPhi_hCooling = aCoolingSystem(intRunNumber).GetCoolingToSpace(currentTimeStep)
    
    ' // ... from primary heating system to hot water
    dblPhi_hWater = aPrimaryHeatingSystem(intRunNumber).GetHeatToHotWater(currentTimeStep)
    
    ' //... from passive solar gains
    dblPhi_s = dblG_o * dblA_s
    aPhi_s(currentTimeStep, 1) = dblPhi_s
    
    ' //... from occupants, lighting and appliances
    dblPhi_cOccupancy = aOccupancy(intRunNumber).GetPhi_cOccupancy((currentTimeStep - 1) \ 10)
    dblPhi_cLighting = aLighting(intRunNumber).GetPhi_cLighting(currentTimeStep)
    dblPhi_cAppliances = aAppliances(intRunNumber).GetPhi_cAppliances(currentTimeStep)
    
    dblPhi_c = dblPhi_cOccupancy + dblPhi_cLighting + dblPhi_cAppliances
    aPhi_c(currentTimeStep, 1) = dblPhi_c
    
    ' // ... from solar thermal collector (if any)
    dblPhi_collector = aSolarThermal(intRunNumber).GetPhi_s(currentTimeStep)
    
    ' // Get the variable hot water demand heat transfer coefficient
    dblH_dhw = aHotWater(intRunNumber).GetH_demand(currentTimeStep)
    'wsMain.Range("M19") = "Appliance number " + CStr(intAppliance) + " Got this far"
    ' // Calculate change in building external thermal node temperatures
    dblDeltaTheta_b = (intTimeStep / dblC_b) * _
                                    ( _
                                        -(dblH_ob + dblH_bi) * dblTheta_b _
                                        + dblH_bi * dblTheta_i _
                                        + dblH_ob * dblTheta_o _
                                    )
    
    ' // Calculate change in building internal thermal node temperatures
    dblDeltaTheta_i = (intTimeStep / dblC_i) * _
                                    ( _
                                        dblH_bi * dblTheta_b _
                                        - (dblH_v + dblH_bi + dblH_em + dblH_cool + dblH_loss) * dblTheta_i _
                                        + dblH_v * dblTheta_o _
                                        + dblH_em * dblTheta_em _
                                        + dblH_cool * dblTheta_cool _
                                        + dblH_loss * dblTheta_cyl _
                                        + dblPhi_s + dblPhi_c _
                                    )
                                    
    ' // Calculate change in heat emitter temperatures (heating radiators only)
    dblDeltaTheta_em = (intTimeStep / dblC_em) * _
                                        ( _
                                            dblH_em * dblTheta_i _
                                            - dblH_em * dblTheta_em _
                                            + dblPhi_hSpace _
                                        )
                                        
    ' // Calculate change in cooler emitter temperatures (cooling coils only)
    dblDeltaTheta_cool = (intTimeStep / dblC_cool) * _
                                        ( _
                                            dblH_cool * dblTheta_i _
                                            - dblH_cool * dblTheta_cool _
                                            + dblPhi_hCooling _
                                        )
    
    ' // Calculate change in temperature of hot water cylinder
    dblDeltaTheta_cyl = (intTimeStep / dblC_cyl) * _
                                        ( _
                                            dblH_loss * dblTheta_i _
                                            - (dblH_loss + dblH_dhw) * dblTheta_cyl _
                                            + dblH_dhw * dblTheta_cw _
                                            + dblPhi_hWater _
                                            + dblPhi_collector _
                                        )
                                        
    ' // Update building thermal node temperatures for this time step
    aTheta_b(currentTimeStep, 1) = dblTheta_b + dblDeltaTheta_b
    aTheta_i(currentTimeStep, 1) = dblTheta_i + dblDeltaTheta_i
    aTheta_em(currentTimeStep, 1) = dblTheta_em + dblDeltaTheta_em
    aTheta_cool(currentTimeStep, 1) = dblTheta_cool + dblDeltaTheta_cool
    aTheta_cyl(currentTimeStep, 1) = dblTheta_cyl + dblDeltaTheta_cyl
    'wsMain.Range("M20") = " Got this far"
End Sub




' ===============================================================================================
' ## WriteBuilding
' Write the simulation output to the sheets
' ===============================================================================================
Public Sub WriteBuilding(dwellingIndexRowOffset As Long)
    
    With wsResultsDisaggregated
        .Range("K7:K1446").Offset(dwellingIndexRowOffset, 0) = aPhi_s
        .Range("M7:M1446").Offset(dwellingIndexRowOffset, 0) = aTheta_b
        .Range("N7:N1446").Offset(dwellingIndexRowOffset, 0) = aTheta_i
        .Range("U7:U1446").Offset(dwellingIndexRowOffset, 0) = aTheta_em
        .Range("P7:P1446").Offset(dwellingIndexRowOffset, 0) = aTheta_cyl
        .Range("H7:H1446").Offset(dwellingIndexRowOffset, 0) = aPhi_c
        .Range("AJ7:AJ1446").Offset(dwellingIndexRowOffset, 0) = aTheta_cool
    End With
End Sub
