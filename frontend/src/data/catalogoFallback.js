// Catálogo de fallback embutido — espelha CATALOGO_MODULOS / CATALOGO_INVERSORES
// de motor_core.py. Usado quando o fetch a /catalogo falha (ex.: cold start do
// Python Worker), garantindo que os seletores de equipamento nunca fiquem vazios.
//
// IMPORTANTE: ao adicionar/alterar equipamentos em motor_core.py, atualizar aqui.

export const CATALOGO_FALLBACK = {
  modulos: [
    { nome: 'CS7N-700TB-AG', Pmpp_Wp: 700.0, fabricante: 'CSI Solar Co., Ltd.', phi: 0.8, eta_pct: 22.53 },
    { nome: 'CS7N-705TB-AG', Pmpp_Wp: 705.0, fabricante: 'CSI Solar Co., Ltd.', phi: 0.8, eta_pct: 22.70 },
    { nome: 'CS7N-710TB-AG', Pmpp_Wp: 710.0, fabricante: 'CSI Solar Co., Ltd.', phi: 0.8, eta_pct: 22.86 },
    { nome: 'CS7N-715TB-AG', Pmpp_Wp: 715.0, fabricante: 'CSI Solar Co., Ltd.', phi: 0.8, eta_pct: 23.02 },
    { nome: 'CS7N-720TB-AG', Pmpp_Wp: 720.0, fabricante: 'CSI Solar Co., Ltd.', phi: 0.8, eta_pct: 23.18 },
    { nome: 'CS7N-725TB-AG', Pmpp_Wp: 725.0, fabricante: 'CSI Solar Co., Ltd.', phi: 0.8, eta_pct: 23.34 },
    { nome: 'CS7N-730TB-AG', Pmpp_Wp: 730.0, fabricante: 'CSI Solar Co., Ltd.', phi: 0.8, eta_pct: 23.50 },
  ],
  inversores: [
    { nome: 'CSI-5K-S22003-E',    P_nomAC_kW: 5.0,   fabricante: 'CSI Solar Co., Ltd.', eta_max_pct: 97.50, N_mppt: 2 },
    { nome: 'CSI-7K-S22003-E',    P_nomAC_kW: 7.0,   fabricante: 'CSI Solar Co., Ltd.', eta_max_pct: 97.50, N_mppt: 2 },
    { nome: 'CSI-9K-S22003-E',    P_nomAC_kW: 9.0,   fabricante: 'CSI Solar Co., Ltd.', eta_max_pct: 97.50, N_mppt: 2 },
    { nome: 'CSI-15K-T4001A-E',   P_nomAC_kW: 15.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 3 },
    { nome: 'CSI-17K-T4001A-E',   P_nomAC_kW: 17.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 3 },
    { nome: 'CSI-20K-T4001A-E',   P_nomAC_kW: 20.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 3 },
    { nome: 'CSI-23K-T4001A-E',   P_nomAC_kW: 23.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 3 },
    { nome: 'CSI-25K-T4001A-E',   P_nomAC_kW: 25.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 3 },
    { nome: 'CSI-40K-T4001A-E',   P_nomAC_kW: 40.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 4 },
    { nome: 'CSI-50K-T2201A-E',   P_nomAC_kW: 50.0,  fabricante: 'CSI Solar Co., Ltd.', eta_max_pct: 99.00, N_mppt: 6 },
    { nome: 'CSI-50K-T4001A-E',   P_nomAC_kW: 50.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 4 },
    { nome: 'CSI-60K-T2201A-E',   P_nomAC_kW: 60.0,  fabricante: 'CSI Solar Co., Ltd.', eta_max_pct: 99.00, N_mppt: 6 },
    { nome: 'CSI-60K-T4001A-E',   P_nomAC_kW: 60.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 98.43, N_mppt: 4 },
    { nome: 'CSI-75K-T2201A-E',   P_nomAC_kW: 75.0,  fabricante: 'CSI Solar Co., Ltd.', eta_max_pct: 99.00, N_mppt: 6 },
    { nome: 'CSI-75K-T40001-E',   P_nomAC_kW: 75.0,  fabricante: 'CSI Solar Inc',       eta_max_pct: 97.50, N_mppt: 4 },
    { nome: 'CSI-100K-T4001A-E',  P_nomAC_kW: 100.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 97.50, N_mppt: 4 },
    { nome: 'CSI-100K-T4001B-E',  P_nomAC_kW: 100.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 97.50, N_mppt: 4 },
    { nome: 'CSI-110K-T4001A-E',  P_nomAC_kW: 110.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 97.50, N_mppt: 4 },
    { nome: 'CSI-110K-T4001B-E',  P_nomAC_kW: 110.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 97.50, N_mppt: 4 },
    { nome: 'CSI-250K-T8001A-E',  P_nomAC_kW: 250.0, fabricante: 'CSI Solar Co., Ltd.', eta_max_pct: 99.00, N_mppt: 8 },
    { nome: 'CSI-333K-T8001A-E',  P_nomAC_kW: 333.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 97.50, N_mppt: 8 },
    { nome: 'CSI-333K-T8001B-E',  P_nomAC_kW: 333.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 97.50, N_mppt: 8 },
    { nome: 'CSI-350K-T8001A-E',  P_nomAC_kW: 350.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 99.01, N_mppt: 8 },
    { nome: 'CSI-350K-T8001B-E',  P_nomAC_kW: 350.0, fabricante: 'CSI Solar Inc',       eta_max_pct: 99.01, N_mppt: 8 },
  ],
}
