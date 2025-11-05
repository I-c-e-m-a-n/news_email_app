import React, { useState } from 'react'

const COUNTRIES = [
  { name: "Australia", code: "au" }, { name: "Brazil", code: "br" },
  { name: "Canada", code: "ca" }, { name: "China", code: "cn" },
  { name: "Egypt", code: "eg" }, { name: "France", code: "fr" },
  { name: "Germany", code: "de" }, { name: "Greece", code: "gr" },
  { name: "Hong Kong", code: "hk" }, { name: "India", code: "in" },
  { name: "Ireland", code: "ie" }, { name: "Israel", code: "il" },
  { name: "Italy", code: "it" }, { name: "Japan", code: "jp" },
  { name: "Netherlands", code: "nl" }, { name: "Norway", code: "no" },
  { name: "Pakistan", code: "pk" }, { name: "Peru", code: "pe" },
  { name: "Philippines", code: "ph" }, { name: "Portugal", code: "pt" },
  { name: "Romania", code: "ro" }, { name: "Russia", code: "ru" },
  { name: "Singapore", code: "sg" }, { name: "Spain", code: "es" },
  { name: "Sweden", code: "se" }, { name: "Switzerland", code: "ch" },
  { name: "Taiwan", code: "tw" }, { name: "Ukraine", code: "ua" },
  { name: "United Kingdom", code: "gb" }, { name: "United States", code: "us" },
]

const CATEGORIES = ["General","World","Nation","Business","Technology","Entertainment","Sports","Science","Health"]

export default function NewsForm() {
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [country, setCountry] = useState("us")
  const [selected, setSelected] = useState([])
  const [apiKey, setApiKey] = useState("")
  const [gmailUser, setGmailUser] = useState("")
  const [gmailPass, setGmailPass] = useState("")

  const toggleCategory = (cat) => {
    setSelected(prev => prev.includes(cat)
      ? prev.filter(c => c !== cat)
      : (prev.length < 4 ? [...prev, cat] : prev)
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const preferences = [country, ...selected]
    try {
      const res = await fetch("https://YOUR-PYTHON-ENDPOINT/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email, name,
          preferences,
          api_key: apiKey,
          gmail_user: gmailUser,
          gmail_pass: gmailPass
        })
      })
      const text = await res.text()
      alert(text)
    } catch (err) {
      alert("Failed to send: " + err.message)
    }
  }

  return (
    <div style={{ maxWidth: 560, margin: "40px auto", padding: 16, border: "1px solid #ddd", borderRadius: 12 }}>
      <h1>News Emailer</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Name<br/>
            <input value={name} onChange={e=>setName(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>Email<br/>
            <input type="email" value={email} onChange={e=>setEmail(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>Country<br/>
            <select value={country} onChange={e=>setCountry(e.target.value)}>
              {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.name}</option>)}
            </select>
          </label>
        </div>

        <div style={{ marginTop: 12 }}>
          <div>Categories (pick up to 4):</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {CATEGORIES.map(cat => (
              <label key={cat}>
                <input
                  type="checkbox"
                  checked={selected.includes(cat)}
                  onChange={() => toggleCategory(cat)}
                /> {cat}
              </label>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <label>Google News API Key<br/>
            <input value={apiKey} onChange={e=>setApiKey(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>Gmail Username<br/>
            <input value={gmailUser} onChange={e=>setGmailUser(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>Gmail App Password<br/>
            <input type="password" value={gmailPass} onChange={e=>setGmailPass(e.target.value)} required />
          </label>
        </div>

        <button type="submit" style={{ marginTop: 16 }}>Fetch & Email News</button>

        <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
          Stored preferences format: [{country}{selected.length ? ", " : ""}{selected.join(", ")}]
        </p>
      </form>
    </div>
  )
}
