import React, { useState } from 'react';

const mockCalls = [
  { id: '1234', status: 'ASR Fail', phone: '090****123', waitTime: '2 phút' },
  { id: '1235', status: 'Out of Scope', phone: '091****456', waitTime: '1 phút' }
];

const OperatorUI: React.FC = () => {
  const [selectedCall, setSelectedCall] = useState<string | null>('1234');

  const handleAcceptHandoff = () => {
    alert('Đã tiếp nhận cuộc gọi. Đang kết nối tổng đài viên với khách hàng...');
  };

  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen flex flex-col">
      {/* Top App Bar */}
      <header className="bg-white border-b border-surface-variant flex justify-between items-center px-6 py-4 w-full sticky top-0 z-10 shadow-sm">
        <div className="flex items-center gap-4">
          <img
            alt="AloSM Logo"
            className="h-10 object-contain"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuA2gLUc8EHxfHwvEi0xYQYF2JBiExB9ngnP0RhARbcS4-8n1lEsjsO1Zob13sgrVBfCHROMa1v7dJ8a8q6C-yqcrzjLrSjZnzZnxZP0B1BtIaloMwzB95w21sCUD1wb0mbNVfE74tOu5r2xczSxwdfqL4vdKlZuiEWaSLCmSaJkHjseigRTFKDDTtjr3j4dcN9ERsqrZyYcOoq5C_NDeAB2akCliYSDY1Yu0qUImvcw707mMzAEAhJN"
          />
          <span className="font-headline-lg text-primary ml-2 border-l-2 pl-4 border-gray-300">Operator Dashboard</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2 font-label-lg">
            <span className="w-3 h-3 rounded-full bg-green-500"></span> Online
          </span>
          <button className="px-4 py-2 bg-surface-container rounded-lg font-label-lg text-error hover:bg-red-50 transition-colors">
            Đăng Xuất
          </button>
        </div>
      </header>

      <main className="flex-grow flex flex-col md:flex-row w-full p-6 gap-6 max-w-[1920px] mx-auto">
        {/* Handoff Queue */}
        <section className="w-full md:w-1/3 flex flex-col gap-4">
          <h2 className="font-headline-lg text-xl flex items-center gap-2">
            <span className="material-symbols-outlined text-status-error">call_received</span>
            Cuộc Gọi Chờ Handoff ({mockCalls.length})
          </h2>

          <div className="flex flex-col gap-4 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 150px)' }}>
            {mockCalls.map((call) => (
              <div
                key={call.id}
                onClick={() => setSelectedCall(call.id)}
                className={`bg-white p-4 rounded-xl border-l-4 shadow-sm cursor-pointer transition-colors ${
                  selectedCall === call.id
                    ? 'border-l-status-error bg-surface-container-low'
                    : 'border-l-gray-300 hover:bg-surface-container-low'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="font-label-lg text-primary">#CALL-{call.id}</span>
                  <span className="bg-red-100 text-status-error px-2 py-1 rounded text-xs font-bold">{call.status}</span>
                </div>
                <p className="font-body-md text-secondary">{call.phone} - Đợi {call.waitTime}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Call Details */}
        <section className="w-full md:w-2/3 flex flex-col">
          {selectedCall ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col h-full overflow-hidden">
              <div className="p-6 border-b border-gray-200 bg-surface-container-low flex justify-between items-center">
                <div>
                  <h3 className="font-headline-lg text-2xl text-primary">#CALL-{selectedCall}</h3>
                  <p className="font-body-md text-secondary mt-1">
                    Lý do: <span className="text-status-error font-bold">Lỗi nhận diện giọng nói (ASR thất bại 2 lần)</span>
                  </p>
                </div>
                <button
                  onClick={handleAcceptHandoff}
                  className="px-8 py-3 bg-primary text-white rounded-lg font-label-lg flex items-center gap-2 hover:bg-teal-700 transition-colors shadow-md"
                >
                  <span className="material-symbols-outlined">headset_mic</span>
                  Tiếp Nhận Cuộc Gọi
                </button>
              </div>

              <div className="p-6 flex-grow flex flex-col gap-6 overflow-y-auto">
                <div>
                  <h4 className="font-label-lg text-gray-500 uppercase mb-2">AI Summary</h4>
                  <div className="bg-blue-50 p-4 rounded-lg border border-blue-100 text-blue-900 font-body-lg">
                    <p>Khách hàng muốn đặt xe nhưng do ồn, AI không nghe rõ địa chỉ điểm đến. Khách đã xác nhận được điểm đón.</p>
                  </div>
                </div>

                <div>
                  <h4 className="font-label-lg text-gray-500 uppercase mb-2">Hành Động Cần Thiết</h4>
                  <div className="bg-red-50 p-4 rounded-lg border border-red-100 text-red-900 font-body-lg flex items-center gap-2">
                    <span className="material-symbols-outlined">warning</span>
                    <span>Hỏi lại điểm đến của khách hàng và tiến hành đặt xe.</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-surface p-4 rounded-lg border border-gray-200">
                    <h4 className="font-label-lg text-gray-500 uppercase mb-4 border-b pb-2">Thông Tin Đã Thu Thập</h4>
                    <div className="flex flex-col gap-3">
                      <div>
                        <span className="text-xs text-gray-500 uppercase block">Intent</span>
                        <span className="font-label-lg">Đặt xe (Booking)</span>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500 uppercase block">Điểm đón (Pickup)</span>
                        <span className="font-label-lg text-primary">Tòa nhà Landmark 81, Bình Thạnh</span>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500 uppercase block">Điểm đến (Destination)</span>
                        <span className="font-label-lg text-status-error">[Chưa có / Mơ hồ]</span>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500 uppercase block">Loại xe (Vehicle)</span>
                        <span className="font-label-lg">4 Chỗ (Mặc định)</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-surface p-4 rounded-lg border border-gray-200 flex flex-col h-full max-h-64 overflow-y-auto">
                    <h4 className="font-label-lg text-gray-500 uppercase mb-4 border-b pb-2 sticky top-0 bg-surface">
                      Transcript Gần Nhất
                    </h4>
                    <div className="flex flex-col gap-2">
                      <p className="text-sm"><strong className="text-primary">AI:</strong> Chào bạn, AloSM xin nghe ạ.</p>
                      <p className="text-sm"><strong className="text-gray-700">User:</strong> Cho mình một xe 4 chỗ ở Landmark 81 đi... (ồn ào)</p>
                      <p className="text-sm"><strong className="text-primary">AI:</strong> Dạ mình đón ở Landmark 81, nhưng điểm đến là ở đâu ạ?</p>
                      <p className="text-sm"><strong className="text-gray-700">User:</strong> (không nghe rõ)</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center bg-gray-50 rounded-xl border border-dashed border-gray-300">
              <p className="text-gray-500 font-label-lg">Chọn một cuộc gọi để xem chi tiết</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
};

export default OperatorUI;
