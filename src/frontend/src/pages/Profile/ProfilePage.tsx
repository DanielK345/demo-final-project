import React from "react";
import {
  Star,
  Edit,
  BadgeCheck,
  CreditCard,
  PlusCircle,
  Wallet,
  Ticket,
  Car,
  Award,
} from "lucide-react";

export const ProfilePage: React.FC = () => {
  const avatarUrl =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuCPe3nQaSaH2LoesASuIwpo9NGrsrW411Rjqiki5KO3ZLKSJfEGU6Cvi3o29yeaNvHUOT8nSIokZQES_pUmT79jnGnemcRnRCgWyiScP0qZ8qpTP_5McgRBN6E4Ydk6kociE4iGSb-MU93C0u0TVDYYi2GCZI8oczdQQ-MLJ038y8ZzCri3YWLEMmICCVI0NPtxefAnMGhfPyAhdM56fDBrdPkpleFt3oA4ApsTIGo4BM-pn72sECis";

  return (
    <div className="max-w-[1024px] mx-auto space-y-8 pb-16">
      {/* Page Header */}
      <header className="mb-2">
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] tracking-tight">
          Tài khoản
        </h1>
      </header>

      {/* Bento Grid Layout for Account Info */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Profile Header Card (8 cols on desktop) */}
        <div className="md:col-span-12 lg:col-span-8 bg-white rounded-2xl p-6 md:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 flex flex-col md:flex-row items-center md:items-start gap-6 relative overflow-hidden group">
          {/* Subtle decor glow */}
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-[#00D1C1]/5 rounded-full blur-3xl group-hover:bg-[#00D1C1]/10 transition-colors duration-500 pointer-events-none" />

          <div className="relative w-24 h-24 md:w-32 md:h-32 rounded-full border-4 border-white shadow-sm overflow-hidden shrink-0 z-10">
            <img
              src={avatarUrl}
              alt="Nguyễn Văn A"
              className="w-full h-full object-cover"
            />
          </div>

          <div className="flex-1 text-center md:text-left z-10 pt-1">
            <h2 className="text-2xl font-extrabold text-[#191C1E] mb-1">Nguyễn Văn A</h2>
            <div className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-[#006a62] text-white text-xs font-semibold shadow-xs mb-4">
              <Star className="w-4 h-4 fill-current text-amber-300" />
              <span>Hạng Thành viên: Platinum</span>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 mt-1">
              <button
                type="button"
                className="bg-[#00D1C1] hover:bg-[#006a62] text-white font-bold text-xs px-6 py-2.5 rounded-[12px] shadow-md shadow-[#00D1C1]/30 hover:-translate-y-0.5 transition-all w-full sm:w-auto text-center flex items-center justify-center gap-2 cursor-pointer"
              >
                <Edit className="w-4 h-4" />
                <span>Edit Profile</span>
              </button>
            </div>
          </div>
        </div>

        {/* Account Information Card (4 cols on desktop) */}
        <div className="md:col-span-12 lg:col-span-4 bg-white rounded-2xl p-6 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 flex flex-col justify-between hover:shadow-md transition-shadow">
          <div>
            <h3 className="text-lg font-bold text-[#191C1E] mb-4 flex items-center gap-2">
              <BadgeCheck className="w-5 h-5 text-slate-500" />
              <span>Thông tin cá nhân</span>
            </h3>

            <div className="space-y-4 text-xs font-medium text-slate-600">
              <div className="flex justify-between items-center border-b border-slate-100 pb-2.5">
                <span className="text-slate-400 font-bold uppercase">Phone</span>
                <span className="font-bold text-[#191C1E]">+84 912 345 678</span>
              </div>
              <div className="flex justify-between items-center border-b border-slate-100 pb-2.5">
                <span className="text-slate-400 font-bold uppercase">Email</span>
                <span className="font-bold text-[#191C1E] truncate max-w-[160px]" title="nguyen.vana@example.com">
                  nguyen.vana@example.com
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400 font-bold uppercase">Date of Birth</span>
                <span className="font-bold text-[#191C1E]">15/08/1990</span>
              </div>
            </div>
          </div>
        </div>

        {/* Payment Methods Section (8 cols on desktop) */}
        <div className="md:col-span-12 lg:col-span-8 bg-white rounded-2xl p-6 md:p-8 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80">
          <div className="flex justify-between items-end mb-6">
            <h3 className="text-lg font-bold text-[#191C1E] flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-slate-500" />
              <span>Phương thức thanh toán</span>
            </h3>
            <button
              type="button"
              className="text-[#00D1C1] hover:text-[#006a62] font-bold text-xs flex items-center gap-1 transition-colors cursor-pointer"
            >
              <PlusCircle className="w-4 h-4" />
              <span className="hidden sm:inline">Add Method</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* AloSM Pay Balance Card */}
            <div className="bg-gradient-to-br from-[#00D1C1] to-[#006a62] text-white rounded-xl p-5 relative overflow-hidden shadow-md group transition-all cursor-pointer">
              <div className="absolute -right-8 -bottom-8 opacity-20">
                <Wallet className="w-32 h-32 text-white" />
              </div>
              <div className="relative z-10 flex flex-col h-full justify-between gap-4">
                <div className="flex items-center gap-2 text-xs font-bold text-white/90">
                  <Wallet className="w-4 h-4" />
                  <span>AloSM Pay Balance</span>
                </div>
                <div>
                  <div className="text-2xl font-extrabold">2,500,000 ₫</div>
                  <div className="text-[10px] text-white/80 mt-1 font-medium">Available to spend</div>
                </div>
              </div>
            </div>

            {/* Linked Visa Card */}
            <div className="bg-slate-50 rounded-xl p-5 border border-slate-200 flex flex-col justify-between gap-4 hover:shadow-md transition-all cursor-pointer">
              <div className="flex justify-between items-start">
                <div className="w-12 h-8 bg-white border border-slate-200 rounded flex items-center justify-center p-1">
                  <span className="text-xs font-extrabold text-blue-800">VISA</span>
                </div>
                <span className="bg-[#00D1C1]/15 text-[#006a62] font-bold text-[10px] px-2 py-0.5 rounded">
                  Default
                </span>
              </div>
              <div>
                <div className="text-sm font-extrabold text-[#191C1E] tracking-widest">
                  •••• •••• •••• 4242
                </div>
                <div className="text-[10px] font-semibold text-slate-400 mt-1">Expires 12/26</div>
              </div>
            </div>
          </div>
        </div>

        {/* Rewards / Coupons Section (4 cols on desktop) */}
        <div className="md:col-span-12 lg:col-span-4 bg-white rounded-2xl p-6 shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/80 flex flex-col h-full">
          <h3 className="text-lg font-bold text-[#191C1E] mb-4 flex items-center gap-2">
            <Ticket className="w-5 h-5 text-slate-500" />
            <span>Ưu đãi của tôi</span>
          </h3>

          <div className="flex-1 space-y-3">
            {/* Coupon 1 */}
            <div className="flex items-center gap-3.5 p-3 rounded-xl border border-[#00D1C1]/30 bg-[#00D1C1]/5 hover:bg-[#00D1C1]/10 transition-colors cursor-pointer group">
              <div className="w-10 h-10 rounded-full bg-[#00D1C1]/20 text-[#006a62] flex items-center justify-center shrink-0">
                <Car className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-[#191C1E] truncate group-hover:text-[#006a62] transition-colors">
                  Giảm 50K chuyến đi tiếp theo
                </div>
                <div className="text-[10px] text-slate-400 font-medium truncate">Hết hạn: Hôm nay</div>
              </div>
            </div>

            {/* Coupon 2 */}
            <div className="flex items-center gap-3.5 p-3 rounded-xl border border-slate-200 bg-slate-50 hover:border-slate-300 transition-colors cursor-pointer group">
              <div className="w-10 h-10 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center shrink-0">
                <Award className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-[#191C1E] truncate group-hover:text-[#006a62] transition-colors">
                  Nâng hạng dịch vụ miễn phí
                </div>
                <div className="text-[10px] text-slate-400 font-medium truncate">
                  Dành riêng cho hạng Platinum
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
