const { telegram_rss } = require("telegram-rss");
const xml2js = require("xml2js");
const http = require("http");

const serverport = process.env.PORT || 8080;

// ==================== КАНАЛЫ ====================
// Добавьте сюда свои каналы (без @)
const telegram_channels = [
  "minskatch",      // ← Ваш канал
  // "durov",
  // "news",
  // Добавьте другие каналы
];

// ==================== ПАРСИНГ RSS ====================

async function parseRssItems(xmlData, channelName) {
  const parser = new xml2js.Parser();
  try {
    const result = await parser.parseStringPromise(xmlData);
    const items = result.rss?.channel?.[0]?.item || [];

    return items.map(item => ({
      channel: channelName,
      title: item.title?.[0] || "",
      link: item.link?.[0] || "",
      description: item.description?.[0] || "",
      pubDate: item.pubDate?.[0] || "",
      date: new Date(item.pubDate?.[0] || 0),
      image: item.image?.[0]?.url?.[0] || null,
      imageTitle: item.image?.[0]?.title?.[0] || null,
      guid: item.guid?.[0] || item.link?.[0] || "",
      author: item.author?.[0] || null,
      category: item.category?.[0] || null
    }));
  } catch (error) {
    console.error(`Error parsing RSS for ${channelName}:`, error.message);
    return [];
  }
}

function escapeXml(unsafe) {
  if (!unsafe) return '';
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function generateRssFeed(items) {
  const rssItems = items.map(item => {
    const imageTag = item.image ? `
      <enclosure url="${escapeXml(item.image)}" type="image/jpeg"/>
      <image>
        <url>${escapeXml(item.image)}</url>
        <title><![CDATA[${item.imageTitle || item.title}]]></title>
        <link>${escapeXml(item.link)}</link>
      </image>` : '';

    return `    <item>
      <title><![CDATA[${item.title}]]></title>
      <link>${escapeXml(item.link)}</link>
      <guid>${escapeXml(item.guid)}</guid>
      <description><![CDATA[[${item.channel}] ${item.description}]]></description>
      <pubDate>${item.pubDate}</pubDate>
      <source>${escapeXml(item.channel)}</source>${imageTag}
    </item>`;
  }).join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Telegram Channels Aggregator</title>
    <link>https://t.me/</link>
    <description>Combined RSS feed from multiple Telegram channels</description>
    <language>en</language>
${rssItems}
  </channel>
</rss>`;
}

function generateJsonResponse(items) {
  return items.map(item => {
    const result = {
      channel: item.channel,
      title: item.title,
      link: item.link,
      description: item.description,
      pubDate: item.pubDate,
      guid: item.guid
    };

    if (item.image) {
      result.image = {
        url: item.image,
        title: item.imageTitle || item.title
      };
    }

    if (item.author) result.author = item.author;
    if (item.category) result.category = item.category;

    return result;
  });
}

// ==================== HTTP СЕРВЕР ====================

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const path = url.pathname.substring(1);
  const format = url.searchParams.get("format");

  try {
    if (!path) {
      const baseUrl = `https://${req.headers.host}`;
      const helpText = `Telegram RSS Aggregator

Available endpoints:
1. GET /crypto - All channels combined
2. GET /{channel_name} - Single channel
3. GET /{channel_name}?format=json - JSON format

Available channels:
${telegram_channels.map((ch, i) => `  ${i + 1}. ${ch}`).join('\n')}

GitHub: https://github.com/yourusername/telegram-bot
`;
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/plain; charset=utf-8");
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.end(helpText);
      return;
    }

    if (path === "crypto") {
      const results = await Promise.allSettled(
        telegram_channels.map(channel =>
          telegram_rss(channel)
            .then(data => ({ channel, data, status: "success" }))
            .catch(err => ({ channel, error: err.message, status: "failed" }))
        )
      );

      const allItems = [];

      for (const result of results) {
        if (result.status === "fulfilled" && result.value.status === "success") {
          const items = await parseRssItems(result.value.data, result.value.channel);
          allItems.push(...items);
        }
      }

      allItems.sort((a, b) => b.date - a.date);

      res.statusCode = 200;
      res.setHeader("Access-Control-Allow-Origin", "*");

      if (format === "json") {
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(JSON.stringify(generateJsonResponse(allItems), null, 2));
      } else {
        res.setHeader("Content-Type", "application/xml; charset=utf-8");
        res.end(generateRssFeed(allItems));
      }
    } else {
      let result = await telegram_rss(path);

      res.statusCode = 200;
      res.setHeader("Access-Control-Allow-Origin", "*");

      if (format === "json") {
        const items = await parseRssItems(result, path);
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(JSON.stringify(generateJsonResponse(items), null, 2));
      } else {
        res.setHeader("Content-Type", "application/xml; charset=utf-8");
        res.end(result);
      }
    }
  } catch (error) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "text/plain");
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.end(`Error: ${error.message}`);
  }
});

// ==================== ЗАПУСК ====================

if (process.env.VERCEL) {
  module.exports = server;
} else {
  server.listen(serverport, () => {
    console.log(`🚀 RSS Aggregator running at port ${serverport}`);
    console.log(`📢 Channels: ${telegram_channels.join(", ")}`);
  });
}
