/* AI Video Factory 0.8.9.0 - chat-style emoji picker.
   Emoji are rasterized by the browser into transparent PNG assets, so render/export
   uses the existing image/sticker pipeline and does not depend on FFmpeg emoji fonts. */
(() => {
  const S = window.Studio;
  if (!S) return;
  const $ = S.$;

  const GROUPS = {
    recent: { icon: '🕘', label: 'Gần đây', items: [] },
    faces: { icon: '😂', label: 'Mặt cười', items: [
      ['😀','cười vui smile happy'],['😃','cười vui happy'],['😄','cười tươi happy'],['😁','cười răng grin'],
      ['😆','cười lớn haha'],['😅','cười mồ hôi'],['😂','cười khóc nước mắt haha lol'],['🤣','cười lăn lộn rofl'],
      ['😊','cười nhẹ dễ thương'],['😇','thiên thần'],['🙂','cười nhẹ'],['🙃','ngược vui'],
      ['😉','nháy mắt wink'],['😌','nhẹ nhõm'],['😍','mắt tim yêu'],['🥰','yêu thương tim'],
      ['😘','hôn kiss'],['😋','ngon yum'],['😛','lè lưỡi'],['😜','nháy mắt lè lưỡi'],
      ['🤪','điên vui crazy'],['🤨','nghi ngờ'],['🧐','soi kính'],['🤓','mọt sách nerd'],
      ['😎','ngầu kính cool'],['🥳','tiệc party'],['😏','cười đểu smirk'],['😒','chán'],
      ['😞','buồn sad'],['😔','buồn'],['😟','lo'],['😕','bối rối'],
      ['🙁','buồn'],['☹️','buồn'],['😣','chịu đựng'],['😖','khó chịu'],
      ['😫','mệt'],['😩','mệt'],['🥺','năn nỉ puppy'],['😢','khóc cry'],
      ['😭','khóc lớn nước mắt cry'],['😤','hừ tức'],['😠','giận angry'],['😡','giận đỏ angry'],
      ['🤬','chửi giận'],['🤯','nổ não shocked'],['😳','ngại đỏ mặt'],['🥵','nóng hot'],
      ['🥶','lạnh cold'],['😱','sợ scream'],['😨','sợ'],['😰','lo mồ hôi'],
      ['😥','buồn nhẹ'],['🤔','suy nghĩ think'],['🤭','che miệng'],['🫢','che miệng sốc'],
      ['🫣','hé mắt'],['🤫','im lặng shh'],['🤥','nói dối'],['😶','im lặng'],
      ['😐','bình thường neutral'],['😑','cạn lời'],['😬','gượng'],['🙄','lườm roll eyes'],
      ['😴','ngủ sleep'],['🤤','chảy dãi'],['😪','buồn ngủ'],['🤢','buồn nôn'],
      ['🤮','nôn'],['🤧','hắt xì'],['🤒','ốm'],['🤕','bị thương']
    ]},
    gestures: { icon: '👍', label: 'Tay & cử chỉ', items: [
      ['👍','like đồng ý tốt'],['👎','dislike không đồng ý'],['👌','ok chuẩn'],['✌️','victory chiến thắng'],
      ['🤞','chúc may mắn'],['🤟','yêu love hand'],['🤘','rock'],['🤙','gọi điện call'],
      ['👈','trái left'],['👉','phải right'],['👆','lên up'],['👇','xuống down'],
      ['☝️','một one'],['✋','dừng stop'],['🤚','tay hand'],['🖐️','năm tay'],
      ['🖖','vulcan'],['👋','vẫy chào hello bye'],['🤏','một chút small'],['💪','cơ bắp mạnh'],
      ['👏','vỗ tay clap'],['🙌','ăn mừng hooray'],['👐','mở tay'],['🤲','hai tay'],
      ['🤝','bắt tay deal'],['🙏','cảm ơn cầu nguyện thanks'],['✍️','viết'],['💅','móng tay'],
      ['👀','mắt nhìn watch'],['👁️','mắt eye'],['👂','tai listen'],['🫶','tay trái tim love']
    ]},
    hearts: { icon: '❤️', label: 'Tim & cảm xúc', items: [
      ['❤️','tim đỏ love yêu'],['🩷','tim hồng'],['🧡','tim cam'],['💛','tim vàng'],['💚','tim xanh lá'],
      ['💙','tim xanh dương'],['🩵','tim xanh nhạt'],['💜','tim tím'],['🤎','tim nâu'],['🖤','tim đen'],
      ['🩶','tim xám'],['🤍','tim trắng'],['💔','vỡ tim broken'],['❤️‍🔥','tim lửa'],['❤️‍🩹','chữa lành'],
      ['💕','hai tim love'],['💞','tim xoay'],['💓','tim đập'],['💗','tim lớn'],['💖','tim lấp lánh'],
      ['💘','mũi tên tình yêu'],['💝','quà tim'],['💟','tim biểu tượng'],['❣️','dấu tim'],['💋','hôn môi kiss'],
      ['💯','100 điểm chuẩn'],['✨','lấp lánh sparkles'],['🔥','lửa hot'],['⭐','sao star'],['🌟','sao sáng']
    ]},
    people: { icon: '🎉', label: 'Phản ứng', items: [
      ['🎉','ăn mừng party'],['🎊','ăn mừng confetti'],['🎂','sinh nhật birthday'],['🎁','quà gift'],
      ['🏆','cúp thắng winner'],['🥇','huy chương vàng'],['🎯','mục tiêu target'],['💥','nổ boom'],
      ['💫','chóng mặt star'],['💦','nước splash'],['💨','gió chạy fast'],['💤','ngủ zzz'],
      ['💬','chat nói'],['🗯️','nói giận'],['💭','suy nghĩ'],['📢','loa thông báo'],
      ['✅','đúng check'],['❌','sai cross'],['❗','chấm than'],['❓','hỏi question'],
      ['‼️','hai chấm than'],['⁉️','hỏi than'],['⚠️','cảnh báo warning'],['🚨','còi báo động'],
      ['🆗','ok'],['🆕','new mới'],['🆒','cool'],['🆙','up'],['🆘','sos'],['🔞','18']
    ]},
    animals: { icon: '🐶', label: 'Động vật', items: [
      ['🐶','chó dog'],['🐱','mèo cat'],['🐭','chuột mouse'],['🐹','hamster'],['🐰','thỏ rabbit'],
      ['🦊','cáo fox'],['🐻','gấu bear'],['🐼','gấu trúc panda'],['🐨','koala'],['🐯','hổ tiger'],
      ['🦁','sư tử lion'],['🐮','bò cow'],['🐷','heo pig'],['🐸','ếch frog'],['🐵','khỉ monkey'],
      ['🙈','khỉ che mắt'],['🙉','khỉ che tai'],['🙊','khỉ che miệng'],['🐔','gà chicken'],['🐧','chim cánh cụt'],
      ['🐦','chim bird'],['🦄','kỳ lân unicorn'],['🐝','ong bee'],['🦋','bướm butterfly'],['🐢','rùa turtle'],
      ['🐍','rắn snake'],['🐙','bạch tuộc'],['🐠','cá fish'],['🐳','cá voi whale'],['🦖','khủng long dinosaur']
    ]},
    food: { icon: '🍔', label: 'Đồ ăn', items: [
      ['🍎','táo apple'],['🍊','cam orange'],['🍋','chanh lemon'],['🍉','dưa hấu watermelon'],['🍇','nho grape'],
      ['🍓','dâu strawberry'],['🍒','cherry'],['🍑','đào peach'],['🥭','xoài mango'],['🍍','dứa pineapple'],
      ['🥑','bơ avocado'],['🌶️','ớt cay hot'],['🍔','burger'],['🍟','khoai tây fries'],['🍕','pizza'],
      ['🌭','hotdog'],['🍗','gà chicken'],['🍜','mì noodles'],['🍚','cơm rice'],['🍣','sushi'],
      ['🍰','bánh cake'],['🍦','kem ice cream'],['🍫','socola chocolate'],['🍿','bắp rang popcorn'],['☕','cà phê coffee'],
      ['🍺','bia drink'],['🥤','nước soda'],['🧋','trà sữa bubble tea']
    ]},
    objects: { icon: '⚡', label: 'Đồ vật & ký hiệu', items: [
      ['⚡','sét lightning'],['💡','ý tưởng idea'],['🔔','chuông bell'],['📌','ghim pin'],['📍','vị trí location'],
      ['🔒','khóa lock'],['🔓','mở khóa unlock'],['🔑','chìa khóa key'],['💎','kim cương diamond'],['💰','tiền money'],
      ['💵','đô la dollar'],['📈','tăng chart up'],['📉','giảm chart down'],['🚀','tên lửa rocket'],['✈️','máy bay plane'],
      ['🚗','xe car'],['🏠','nhà home'],['📱','điện thoại phone'],['💻','máy tính laptop'],['🎮','game controller'],
      ['🎧','tai nghe headphones'],['📷','camera'],['🎬','video movie'],['🎵','nhạc music'],['🎤','microphone'],
      ['🛠️','công cụ tools'],['⚙️','cài đặt settings'],['🧲','nam châm magnet'],['🧨','pháo firecracker'],['🏁','cờ đích finish']
    ]}
  };

  const RECENT_KEY = 'aivf_recent_emojis_v1';
  let activeCategory = 'faces';

  function recentList() {
    try {
      const parsed = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
      return Array.isArray(parsed) ? parsed.filter(Boolean).slice(0, 28) : [];
    } catch (_) { return []; }
  }

  function remember(emoji) {
    const list = recentList().filter(x => x !== emoji);
    list.unshift(emoji);
    localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 28)));
  }

  function allEntries() {
    return Object.entries(GROUPS).filter(([k]) => k !== 'recent').flatMap(([group, meta]) =>
      meta.items.map(([emoji, keywords]) => ({emoji, keywords: `${keywords} ${meta.label} ${group}`}))
    );
  }

  function categoryEntries(category) {
    if (category === 'recent') {
      const all = new Map(allEntries().map(x => [x.emoji, x]));
      return recentList().map(e => all.get(e) || {emoji:e, keywords:'gần đây recent'});
    }
    return (GROUPS[category]?.items || []).map(([emoji, keywords]) => ({emoji, keywords}));
  }

  function renderCategories() {
    const box = $('emojiCategories');
    if (!box) return;
    box.innerHTML = '';
    Object.entries(GROUPS).forEach(([key, meta]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'emoji-category'; b.dataset.category = key;
      b.textContent = meta.icon; b.title = meta.label;
      b.classList.toggle('active', key === activeCategory);
      b.onclick = () => { activeCategory = key; $('emojiSearch').value = ''; renderCategories(); renderEmojiGrid(); };
      box.appendChild(b);
    });
  }

  function renderEmojiGrid() {
    const grid = $('emojiGrid');
    if (!grid) return;
    const q = ($('emojiSearch')?.value || '').trim().toLocaleLowerCase('vi');
    const entries = q ? allEntries().filter(x => `${x.emoji} ${x.keywords}`.toLocaleLowerCase('vi').includes(q)) : categoryEntries(activeCategory);
    grid.innerHTML = '';
    if (!entries.length) {
      grid.innerHTML = '<div class="emoji-empty">Không thấy emoji phù hợp.</div>';
      return;
    }
    entries.forEach(({emoji, keywords}) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'emoji-item'; b.textContent = emoji;
      b.title = keywords.split(' ').slice(0, 5).join(' ');
      b.onclick = () => insertEmoji(emoji);
      grid.appendChild(b);
    });
  }

  function emojiFileName(emoji) {
    const cp = [...emoji].map(c => c.codePointAt(0).toString(16)).join('-');
    return `emoji_${cp}.png`;
  }

  function emojiToPng(emoji) {
    return new Promise((resolve, reject) => {
      const canvas = document.createElement('canvas');
      canvas.width = 320; canvas.height = 320;
      const ctx = canvas.getContext('2d');
      if (!ctx) return reject(new Error('Trình duyệt không hỗ trợ Canvas'));
      ctx.clearRect(0,0,320,320);
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.font = '230px "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif';
      ctx.fillText(emoji, 160, 174, 288);
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Không tạo được PNG emoji')), 'image/png');
    });
  }

  async function insertEmoji(emoji) {
    if (!S.hasVideo()) return S.setStatus('Tải video lên trước rồi mới chèn emoji.', true);
    try {
      const blob = await emojiToPng(emoji);
      remember(emoji); renderCategories();
      const file = new File([blob], emojiFileName(emoji), {type:'image/png'});
      await S.uploadAsset(file, 'sticker');
      S.setStatus(`Đã chèn ${emoji} vào video. Kéo để đổi vị trí.`);
    } catch (e) {
      S.setStatus('Không chèn được emoji: ' + e.message, true);
    }
  }

  function selectTab(tab) {
    document.querySelectorAll('[data-sticker-tab]').forEach(b => b.classList.toggle('active', b.dataset.stickerTab === tab));
    $('stickerEmoji')?.classList.toggle('hidden', tab !== 'emoji');
    $('stickerCustom')?.classList.toggle('hidden', tab !== 'custom');
    $('stickerLocal')?.classList.toggle('hidden', tab !== 'local');
    $('stickerGiphy')?.classList.toggle('hidden', tab !== 'giphy');
  }

  document.querySelectorAll('[data-sticker-tab]').forEach(b => b.onclick = () => selectTab(b.dataset.stickerTab));
  if ($('emojiSearch')) $('emojiSearch').oninput = renderEmojiGrid;
  renderCategories(); renderEmojiGrid(); selectTab('emoji');

  window.AIVFEmojiPicker = {insertEmoji, renderEmojiGrid, selectTab};
})();
