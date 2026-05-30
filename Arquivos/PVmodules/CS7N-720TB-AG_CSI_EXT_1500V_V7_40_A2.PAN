PVObject_=pvModule
  Version=7.4.2
  Flags=$00900143

  PVObject_Commercial=pvCommercial
    Comment=www.csisolar.com
    Flags=$0041
    Manufacturer=CSI Solar Co., Ltd.
    Model=CS7N-720TB-AG 1500V
    DataSource=Manufacturer 2024 TUV-SUD data
    YearBeg=2024
    Width=1.303
    Height=2.384
    Depth=0.033
    Weight=37.800
    NPieces=0
    PriceDate=22/07/16 16:29
    Currency=EUR
    Remarks, Count=5
      Str_1=Frame: Anodized aluminium alloy
      Str_2=Front glass: 2.0 mm heat strengthened glass with anti-
      Str_3=reflective coating
      Str_4=Back glass:  2.0 mm heat strengthened glass
      Str_5=Connections: Cable,T6 or MC4-EVO2 or MC4-EVO2A
    End of Remarks=Connections: Cable,T6 or MC4-EVO2 or MC4-EVO2A
  End of PVObject pvCommercial

  Technol=mtSiMono
  NCelS=66
  NCelP=2
  NDiode=3
  SubModuleLayout=slTwinHalfCells
  GRef=1000
  TRef=25.0
  PNom=720.0
  PNomTolLow=0.00
  PNomTolUp=1.40
  BifacialityFactor=0.800
  Isc=18.690
  Voc=48.70
  Imp=17.670
  Vmp=40.80
  muISC=9.32
  muVocSpec=-119.2
  muPmpReq=-0.290
  RShunt=200
  Rp_0=90000
  Rp_Exp=9.00
  RSerie=0.135
  Gamma=1.043
  muGamma=-0.0004
  VMaxIEC=1500
  VMaxUL=1500
  Absorb=0.90
  ARev=3.200
  BRev=11.600
  RDiode=0.010
  VRevDiode=-0.70
  AirMassRef=1.500
  SandiaAMCorr=50.000
  RelEffic800=0.40
  RelEffic400=0.10
  RelEffic200=-1.20

  PVObject_IAM=pvIAM
    Flags=$00
    IAMMode=UserProfile
    IAMProfile=TCubicProfile
      NPtsMax=9
      NPtsEff=9
      LastCompile=$B18D
      Mode=3
      Point_1=20.0,1.00000
      Point_2=40.0,1.00000
      Point_3=60.0,1.00000
      Point_4=65.0,0.99000
      Point_5=70.0,0.96000
      Point_6=75.0,0.92000
      Point_7=80.0,0.84000
      Point_8=85.0,0.72000
      Point_9=90.0,0.00000
    End of TCubicProfile
  End of PVObject pvIAM

  OperPoints, list of=4 tOperPoint
    Point_1=True,1000,25.0,0.00,48.70,18.690,17.670,40.80,720.94
    Point_2=False,800,25.0,0.40,0.00,0.000,0.000,0.00,579.06
    Point_3=False,400,25.0,0.10,0.00,0.000,0.000,0.00,288.66
    Point_4=False,200,25.0,-1.20,0.00,0.000,0.000,0.00,142.46
  End of List OperPoints
End of PVObject pvModule
