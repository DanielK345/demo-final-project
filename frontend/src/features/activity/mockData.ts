export interface ActivityCardData {
  id: string;
  status: "completed" | "cancelled";
  statusText: string;
  time: string;
  pickup: string;
  destination: string;
  price: string;
  mapImage: string;
}

export const MOCK_TRIP_HISTORY: ActivityCardData[] = [
  {
    id: "trip-1",
    status: "completed",
    statusText: "Hoàn thành",
    time: "Hôm nay, 14:30",
    pickup: "Vincom Center Landmark 81, 720A Điện Biên Phủ, Phường 22, Bình Thạnh",
    destination: "Nhà hát Thành phố, 7 Công Trường Lam Sơn, Bến Nghé, Quận 1",
    price: "125.000đ",
    mapImage:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuCrnjqoAATi3XRNoyK4OTmflTniEwK_D0KhIwhxwbeg_TwJlllZjjjgziV0sDKtzOCnlcidkOOmOOfh8_nTgfzNdMxJdBPkVpBs2d9b001exilkfuShHNPKi3jI1zFoE0kwZ-Dd4zEAZn8jVNPOvjFMWLFqKRVM2jA-6_mvaBSvIyyAhGwefKesMjRsQbnuS2IUjCmcg9cHjRY5zV_QveO9bpR0XLnclPWbJrK15xWHGu6D2gGspu0F",
  },
  {
    id: "trip-2",
    status: "cancelled",
    statusText: "Đã hủy",
    time: "Hôm qua, 09:15",
    pickup: "Sân bay Quốc tế Tân Sơn Nhất, Phường 2, Tân Bình",
    destination: "Khách sạn Caravelle, 19-23 Công Trường Lam Sơn, Bến Nghé, Quận 1",
    price: "185.000đ",
    mapImage:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuDGKBeToWmUcXiTA7a0upsc-iSFr0XH7t-jPw5_H4R3B0qzusVc4Lhx5HnwR1wTVKAwIa0ZTK4JZ7fZvehRqBFZjKccV9CT1qOPdjBTSrc_1HVmbt29_MHUhHKdIZxurV54yRnY6xJej6fEo0SJmXkzcV3Fv5mtL1kKfo3rk-bQ4NUk5Rn0cGJX03G1ouk6LW393dw1F0_G7ZjoeambyvN96iPTVPgMntD-n1i0SUcnftvA-2xIiV-O",
  },
  {
    id: "trip-3",
    status: "completed",
    statusText: "Hoàn thành",
    time: "12/10/2023, 18:45",
    pickup: "Crescent Mall, 101 Tôn Dật Tiên, Tân Phú, Quận 7",
    destination: "Khu dân cư Masteri Thảo Điền, 159 Xa lộ Hà Nội, Thảo Điền, Quận 2",
    price: "210.000đ",
    mapImage:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuC_epFxketkt98EP9AsElvKEd8evRMo2Erd_xz8-dD347oiKNx3z1z8nQrHqxtmbJOffIDmzy6iT6JRiBq0fiC72cXS1mYEM0ila3apkqlaYAD6z907ARiwmV-g-y4LJZBcun80nY6X3Hoq0cmFbjVOVULxI5mMPiu1U0lWzPsu3TLrFMNnJKg5St7HuY0FCgxOZ2xtaSRauDnaI3flN_mpbFFNumvaBZ_VKxFrlp9H_qnNptD4lDHv",
  },
];
