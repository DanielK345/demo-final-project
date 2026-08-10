import React, { useState } from 'react';

type UIState = 'ready' | 'listening' | 'processing' | 'speaking';
type ModalStep = 'none' | 'confirm' | 'success';

interface TranscriptItem {
  id: number;
  role: 'ai' | 'user';
  text: string;
}

const CustomerUI: React.FC = () => {
  const [uiState, setUiState] = useState<UIState>('listening');
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([
    { id: 1, role: 'ai', text: 'Chào bạn, tôi là trợ lý ảo AloSM. Bạn muốn đặt xe đi đâu ạ?' },
    { id: 2, role: 'user', text: 'Tôi muốn đặt một chiếc xe đi Bệnh viện Vinmec Times City...' }
  ]);
  const [pickup, setPickup] = useState('Khu đô thị Vinhomes Riverside, Long Biên');
  const [destination, setDestination] = useState('Bệnh viện Vinmec Times City');
  const [vehicle, setVehicle] = useState('Taxi AloSM (4 Chỗ)');
  const [modalStep, setModalStep] = useState<ModalStep>('none');

  const isCallActive = uiState !== 'ready';

  const isReadyForBooking =
    pickup !== 'Đang xác định...' &&
    destination !== 'Chưa có thông tin';

  const handleStartCall = () => {
    console.log('Đã cấp quyền mic. Bắt đầu kết nối WebSocket...');
    setUiState('listening');
    setTranscripts([]);
    setTimeout(() => {
      setTranscripts([
        { id: 1, role: 'ai', text: 'Chào bạn, tôi là trợ lý ảo AloSM. Bạn muốn đặt xe đi đâu ạ?' }
      ]);
    }, 1000);
  };

  const handleEndCall = () => {
    setUiState('ready');
    setTranscripts([]);
    setPickup('Đang xác định...');
    setDestination('Chưa có thông tin');
    setVehicle('Đang cập nhật...');
    setModalStep('none');
  };

  const statusLabel = () => {
    switch (uiState) {
      case 'ready': return 'Sẵn sàng';
      case 'listening': return 'Hệ thống đang nghe...';
      case 'processing': return 'Đang xử lý...';
      case 'speaking': return 'AI đang nói...';
    }
  };

  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen flex flex-col">
      {/* Top App Bar */}
      <header className="bg-white border-b border-surface-variant flex justify-between items-center px-gutter py-4 w-full sticky top-0 z-10 shadow-sm">
        <div className="flex items-center gap-4">
          <img
            alt="AloSM Logo"
            className="h-10 md:h-12 object-contain"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuA2gLUc8EHxfHwvEi0xYQYF2JBiExB9ngnP0RhARbcS4-8n1lEsjsO1Zob13sgrVBfCHROMa1v7dJ8a8q6C-yqcrzjLrSjZnzZnxZP0B1BtIaloMwzB95w21sCUD1wb0mbNVfE74tOu5r2xczSxwdfqL4vdKlZuiEWaSLCmSaJkHjseigRTFKDDTtjr3j4dcN9ERsqrZyYcOoq5C_NDeAB2akCliYSDY1Yu0qUImvcw707mMzAEAhJN"
          />
        </div>
        <div className="flex items-center gap-4">
          <button className="h-touch-target px-6 flex items-center justify-center gap-2 rounded-full border-2 border-primary text-primary font-label-lg hover:bg-surface-container transition-colors">
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>help</span>
            <span className="hidden md:inline">Trợ Giúp</span>
          </button>
        </div>
      </header>

      <main className="flex-grow flex flex-col md:flex-row max-w-[1920px] mx-auto w-full p-4 md:p-gutter gap-gutter">
        {/* Left/Main Column: Interaction Area */}
        <section className="flex-1 flex flex-col gap-6 w-full max-w-3xl mx-auto">
          {/* Main Voice Interaction Control */}
          <div className="bg-white rounded-xl border border-surface-variant p-8 md:p-12 flex flex-col items-center justify-center min-h-[400px] shadow-sm relative overflow-hidden">
            {/* Status Indicator */}
            <div className="absolute top-6 left-6 flex items-center gap-3">
              <div className={`w-4 h-4 rounded-full ${isCallActive ? 'bg-status-listening animate-pulse' : 'bg-gray-400'}`}></div>
              <span className="font-label-lg text-primary">{statusLabel()}</span>
            </div>

            {/* Central Button */}
            <button
              onClick={!isCallActive ? handleStartCall : undefined}
              className="w-48 h-48 rounded-full bg-primary flex flex-col items-center justify-center text-white pulse-animation hover:bg-tertiary transition-colors active:scale-95 shadow-lg mb-8"
            >
              <span className="material-symbols-outlined text-[64px] mb-2" style={{ fontVariationSettings: "'FILL' 1" }}>mic</span>
              <span className="font-headline-lg-mobile text-headline-lg-mobile">Nói Ngay</span>
            </button>

            {/* Mic Waves */}
            {isCallActive && (
              <div className="flex gap-2 mic-waves h-8 items-center text-primary-container">
                <span className="w-1.5 bg-current rounded-full inline-block"></span>
                <span className="w-1.5 bg-current rounded-full inline-block"></span>
                <span className="w-1.5 bg-current rounded-full inline-block"></span>
              </div>
            )}

            {/* Real-time Transcript */}
            {isCallActive && transcripts.length > 0 && (
              <div className="w-full flex flex-col gap-4 mb-6">
                {transcripts.map((t) => (
                  <div key={t.id} className={`flex flex-col ${t.role === 'ai' ? 'items-start' : 'items-end'}`}>
                    <span className={`font-label-sm text-label-sm text-secondary mb-1 ${t.role === 'ai' ? 'ml-2' : 'mr-2'}`}>
                      {t.role === 'ai' ? 'AloSM AI' : 'Bạn'}
                    </span>
                    <div className={`p-4 rounded-xl max-w-[85%] shadow-sm ${
                      t.role === 'ai'
                        ? 'bg-primary text-white rounded-tl-none'
                        : 'bg-surface-container-high text-on-surface rounded-tr-none'
                    }`}>
                      <p className="font-body-md text-body-md">{t.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Latest Transcript Box */}
            {isCallActive && transcripts.length > 0 && (
              <div className="mt-8 w-full bg-surface-container-low rounded-lg p-6 min-h-[120px] border border-outline-variant">
                <p className="font-headline-lg-mobile text-headline-lg-mobile md:font-headline-lg md:text-headline-lg text-on-surface text-center opacity-80 leading-relaxed">
                  "{transcripts[transcripts.length - 1].text}"
                </p>
              </div>
            )}

            {/* End Call Button */}
            {isCallActive && (
              <div className="mt-6 flex justify-center w-full">
                <button
                  onClick={handleEndCall}
                  className="h-touch-target px-8 rounded-full border-2 border-error text-error font-label-lg text-label-lg hover:bg-error-container transition-colors flex items-center gap-2"
                >
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>call_end</span>
                  Kết Thúc Gọi
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Right Column: Booking Details Card */}
        <section className="w-full md:w-[450px] shrink-0 flex flex-col">
          <div className="bg-white rounded-xl border border-surface-variant shadow-sm h-full flex flex-col overflow-hidden">
            <div className="bg-primary-container p-6 text-on-primary-container flex items-center gap-4">
              <span className="material-symbols-outlined text-[32px]">local_taxi</span>
              <h2 className="font-headline-lg-mobile text-headline-lg-mobile m-0">Chi Tiết Đặt Xe</h2>
            </div>

            <div className="p-6 flex-grow flex flex-col gap-6">
              {/* Pickup */}
              <div className="flex items-start gap-4 p-4 bg-surface rounded-lg border border-surface-variant">
                <div className="bg-white p-2 rounded-full shadow-sm text-primary">
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>my_location</span>
                </div>
                <div>
                  <p className="font-label-sm text-label-sm text-secondary uppercase mb-1">Điểm Đón</p>
                  <p className="font-body-xl text-body-xl text-on-surface">{pickup}</p>
                </div>
              </div>

              {/* Separator */}
              <div className="flex justify-center -my-3 z-10 relative">
                <span className="material-symbols-outlined text-outline bg-white rounded-full p-1 border border-surface-variant">more_vert</span>
              </div>

              {/* Destination */}
              <div className="flex items-start gap-4 p-4 bg-surface rounded-lg border border-surface-variant">
                <div className="bg-white p-2 rounded-full shadow-sm text-status-error">
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>location_on</span>
                </div>
                <div>
                  <p className="font-label-sm text-label-sm text-secondary uppercase mb-1">Điểm Đến</p>
                  <p className="font-body-xl text-body-xl text-on-surface font-semibold text-primary">{destination}</p>
                </div>
              </div>

              {/* Vehicle Details */}
              <div className="mt-4 p-4 bg-surface-container-low rounded-lg border border-outline-variant flex items-center gap-4">
                <span className="material-symbols-outlined text-[40px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>electric_car</span>
                <div>
                  <p className="font-body-xl text-body-xl font-semibold">{vehicle}</p>
                  <p className="font-body-md text-body-md text-secondary">Xe điện êm ái, thân thiện môi trường</p>
                </div>
              </div>
            </div>

            {/* CTA */}
            <div className="p-6 border-t border-surface-variant bg-surface-container-lowest">
              <button
                disabled={!isReadyForBooking}
                onClick={() => setModalStep('confirm')}
                className={`w-full h-touch-target bg-primary text-white rounded-full font-label-lg text-label-lg flex items-center justify-center gap-2 transition-colors shadow-md ${
                  isReadyForBooking ? 'hover:bg-tertiary' : 'opacity-50 cursor-not-allowed'
                }`}
              >
                <span className="material-symbols-outlined">check_circle</span>
                {isReadyForBooking ? 'Xác Nhận Đặt Xe (Dự kiến 52.000đ)' : 'Chờ thông tin đặt xe...'}
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* STEP 1: Confirmation Modal ("Xác nhận đặt xe?") */}
      {modalStep === 'confirm' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-gutter bg-on-background/40 backdrop-blur-sm">
          <div aria-labelledby="modal-title" aria-modal="true" className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col border border-surface-container-high" role="dialog">
            {/* Header with Logo */}
            <div className="p-8 border-b border-surface-container flex flex-col items-center justify-center bg-surface-bright text-center">
              <img
                alt="AloSM Logo"
                className="h-16 md:h-20 mb-6 object-contain"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuA2gLUc8EHxfHwvEi0xYQYF2JBiExB9ngnP0RhARbcS4-8n1lEsjsO1Zob13sgrVBfCHROMa1v7dJ8a8q6C-yqcrzjLrSjZnzZnxZP0B1BtIaloMwzB95w21sCUD1wb0mbNVfE74tOu5r2xczSxwdfqL4vdKlZuiEWaSLCmSaJkHjseigRTFKDDTtjr3j4dcN9ERsqrZyYcOoq5C_NDeAB2akCliYSDY1Yu0qUImvcw707mMzAEAhJN"
              />
              <h1 className="font-headline-xl-mobile text-headline-xl-mobile md:font-headline-xl md:text-headline-xl text-primary font-bold" id="modal-title">
                Xác nhận đặt xe?
              </h1>
            </div>

            {/* Booking Details Content */}
            <div className="p-8 flex flex-col gap-8 bg-white">
              {/* Pickup */}
              <div className="flex items-start gap-6">
                <div className="flex-shrink-0 mt-1 h-12 w-12 rounded-full bg-surface-container flex items-center justify-center text-secondary">
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>my_location</span>
                </div>
                <div className="flex-1">
                  <p className="font-label-sm text-label-sm text-secondary uppercase tracking-wider mb-2">Điểm đón</p>
                  <p className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface font-bold">{pickup}</p>
                </div>
              </div>

              {/* Divider */}
              <div className="h-px bg-surface-variant w-full ml-18 relative">
                <div className="absolute -top-3 left-6 h-6 w-px bg-surface-variant hidden md:block"></div>
              </div>

              {/* Destination */}
              <div className="flex items-start gap-6">
                <div className="flex-shrink-0 mt-1 h-12 w-12 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center">
                  <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>location_on</span>
                </div>
                <div className="flex-1">
                  <p className="font-label-sm text-label-sm text-secondary uppercase tracking-wider mb-2">Điểm đến</p>
                  <p className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface font-bold">{destination}</p>
                </div>
              </div>

              {/* Price Highlight */}
              <div className="mt-4 p-6 bg-surface-container-low rounded-lg border border-surface-variant flex justify-between items-center">
                <span className="font-body-xl text-body-xl text-on-surface-variant">Giá cước ước tính:</span>
                <span className="font-headline-lg text-headline-lg text-primary font-bold">52,000đ</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="p-6 md:p-8 bg-surface-container-lowest border-t border-surface-variant flex flex-col md:flex-row gap-4">
              <button
                type="button"
                aria-label="Hủy đặt xe"
                onClick={() => setModalStep('none')}
                className="flex-1 min-h-[56px] px-8 rounded-lg border-2 border-outline text-on-surface font-label-lg text-label-lg uppercase tracking-wide hover:bg-surface-container focus:ring-4 focus:ring-surface-variant transition-colors flex items-center justify-center"
              >
                Hủy
              </button>
              <button
                type="button"
                aria-label="Xác nhận đặt xe"
                onClick={() => setModalStep('success')}
                className="flex-1 min-h-[56px] px-8 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg uppercase tracking-wide hover:bg-tertiary focus:ring-4 focus:ring-primary-container transition-colors shadow-md flex items-center justify-center gap-2"
              >
                <span>Xác nhận</span>
                <span className="material-symbols-outlined">check_circle</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STEP 2: Booking Success Modal */}
      {modalStep === 'success' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-on-background/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full overflow-hidden flex flex-col">
            <div className="bg-primary p-8 flex flex-col items-center justify-center text-white text-center">
              <span className="material-symbols-outlined text-[72px] mb-4" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
              <h3 className="font-headline-lg-mobile text-headline-lg-mobile">Đặt Xe Thành Công!</h3>
            </div>
            <div className="p-8 text-center flex flex-col gap-4">
              <p className="font-body-xl text-body-xl text-on-surface">Tài xế Nguyễn Văn A đang trên đường đến đón bạn.</p>
              <div className="bg-surface p-4 rounded-lg border border-surface-variant">
                <p className="font-headline-lg text-headline-lg text-primary">29A - 123.45</p>
                <p className="font-body-md text-body-md text-secondary">VinFast VF e34 - Xanh Mint</p>
              </div>
              <p className="font-body-lg text-body-lg text-status-connecting flex items-center justify-center gap-2 mt-2">
                <span className="material-symbols-outlined animate-spin">schedule</span>
                Dự kiến đón sau 3 phút
              </p>
            </div>
            <div className="p-4 border-t border-surface-variant bg-surface-container-lowest flex justify-center">
              <button
                onClick={() => setModalStep('none')}
                className="h-touch-target px-12 bg-surface text-primary border-2 border-primary rounded-full font-label-lg text-label-lg hover:bg-primary hover:text-white transition-colors w-full"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomerUI;
