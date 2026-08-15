import { Users, Snowflake, Wifi, Zap } from "lucide-react";

// Đúng 3 loại xe thật có thể đặt được qua Agentic AI (Core Agent, nhánh
// feature/agentic-ai, xem src/agents/booking_types.py::VehicleType) — không còn
// "hạng sang/Premium" như bản cũ (nhánh đó không có loại này), thay bằng "xe máy"
// (đúng chuẩn phân loại xe ôm công nghệ ở Việt Nam). id khớp thẳng với giá trị
// VehicleType thật để câu prefill gửi sang AI Assistant luôn đặt được đúng loại xe.
export interface ServiceOptionItem {
  id: "MOTORBIKE" | "CAR_4" | "CAR_7";
  name: string;
  badge?: string;
  description: string;
  startingPrice: string;
  basePrice: number;
  features: {
    icon: any;
    label: string;
  }[];
  image: string;
}

export const MOCK_SERVICES_CATALOG: ServiceOptionItem[] = [
  {
    id: "MOTORBIKE",
    name: "AloSM Bike",
    description: "Xe máy công nghệ — len lỏi nội thành, tới nơi nhanh nhất giờ cao điểm.",
    startingPrice: "15.000đ",
    basePrice: 15000,
    features: [
      { icon: Users, label: "1 Chỗ" },
      { icon: Zap, label: "Nhanh, tránh kẹt xe" },
    ],
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuD7of9C71Y0PM7m2A3OAOdafrsiq4wMJR04pRVL6NcI-PaMGCLeBNrXajbfPeJsTBAgfqAR4wlLEteFFPatGPPRTr2raFiOq9yWKttSRhWDqJ16jXeGdr6zFtumVBD52IkH5X5IrNnfcxaIC5sLDClZMgsFT4VVxL4HRBpn_rSt52h-4qg9pXtPqdc3iJ-1HXNG-SyXdup2WV9HRzrfrBx_NmUT6EFHOpgkgArP-nM08UvOdppfPcoe",
  },
  {
    id: "CAR_4",
    name: "AloSM Taxi",
    description: "Di chuyển hàng ngày nhanh chóng, tiết kiệm và thân thiện môi trường.",
    startingPrice: "25.000đ",
    basePrice: 25000,
    features: [
      { icon: Users, label: "4 Chỗ" },
      { icon: Snowflake, label: "Điều hòa mát mẻ" },
    ],
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuDDleAnoPL8CVptZo7Tc64Ofsn9nXCqHv73ntbUGuaeg3YmYJU2CTLBhD7htOAH_y2uGsf6fwu5L8deyFwtjZvkP9NevrS7sg5MLxIQpie47Aku6yyF_4psoIb8njm9sHcPGpiDkdtwfOcDff9sfG_99MDSyUBk2xPZCB0zIsbFssM550VkfTPkXO9p9ZhCWAmd9perx9KnG3_ep4v-fR0105pW1JyACdI5iOuEGqCLH5kgeLSQgWpt",
  },
  {
    id: "CAR_7",
    name: "AloSM Plus",
    description: "Không gian rộng rãi, tiện nghi cao cấp. Phù hợp cho gia đình và công việc.",
    startingPrice: "30.000đ",
    basePrice: 30000,
    features: [
      { icon: Users, label: "7 Chỗ" },
      { icon: Wifi, label: "Wi-Fi & Sạc miễn phí" },
    ],
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuDZBy15NM2vBICkhPfQzyIrsuuW5AN8-k9FA8ug4KXDGmVqgYQP7IH3YkP1KT-tgZsNUHkLglHcj-mP6NZNGZHS_aA8mEKvv2vL1GcnJsLwxyiiRJ9VZkqYvsN4mOax-6UXIHKGmeb9PBmSSmI5DeP4rE4Tf95fdrZ3ywZ7WjV9XxNWlPwmUGltDUGx5GkiqTBqxotaViB4pDPD4CQOmaVyVZSUdXLzcuGZOXqgZRS5CzMsfPfwjU0O",
  },
];
