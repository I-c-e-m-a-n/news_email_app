import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select"

const COUNTRIES = [
  { name: "Australia", code: "au" },
  { name: "Brazil", code: "br" },
  { name: "Canada", code: "ca" },
  { name: "China", code: "cn" },
  { name: "Egypt", code: "eg" },
  { name: "France", code: "fr" },
  { name: "Germany", code: "de" },
  { name: "Greece", code: "gr" },
  { name: "Hong Kong", code: "hk" },
  { name: "India", code: "in" },
  { name: "Ireland", code: "ie" },
  { name: "Israel", code: "il" },
  { name: "Italy", code: "it" },
  { name: "Japan", code: "jp" },
  { name: "Netherlands", code: "nl" },
  { name: "Norway", code: "no" },
  { name: "Pakistan", code: "pk" },
  { name: "Peru", code: "pe" },
  { name: "Philippines", code: "ph" },
  { name: "Portugal", code: "pt" },
  { name: "Romania", code: "ro" },
  { name: "Russia", code: "ru" },
  { name: "Singapore", code: "sg" },
  { name: "Spain", code: "es" },
  { name: "Sweden", code: "se" },
  { name: "Switzerland", code: "ch" },
  { name: "Taiwan", code: "tw" },
  { name: "Ukraine", code: "ua" },
  { name: "United Kingdom", code: "gb" },
  { name: "United States", code: "us" },
]

const CATEGORIES = [
  "General", "World", "Nation", "Business", "Technology", "Entertainment", "Sports", "Science", "Health"
]

export default function NewsForm() {
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [country, setCountry] = useState("us")
  const [selectedCategories, setSelectedCategories] = useState([])
  const [apiKey, setApiKey] = useState("")
  const [gmailUser, setGmailUser] = useState("")
  const [gmailPass, setGmailPass] = useState("")

  const handleCheckbox = (category) => {
    setSelectedCategories(prev => {
      if (prev.includes(category)) return prev.filter(c => c !== category)
      if (prev.length >= 4) return prev
      return [...prev, category]
    })
  }

  const handleSubmit = async () => {
    const data = {
      email,
      name,
      preferences: [country, ...selectedCategories],
      api_key: apiKey,
      gmail_user: gmailUser,
      gmail_pass: gmailPass
    }
    const response = await fetch("https://your-python-endpoint.com/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    })
    const result = await response.text()
    alert(result)
  }

  return (
    <Card className="max-w-xl mx-auto mt-10 p-6">
      <CardContent className="space-y-4">
        <Input placeholder="Your Name" value={name} onChange={e => setName(e.target.value)} />
        <Input placeholder="Your Email" value={email} onChange={e => setEmail(e.target.value)} />
        <Select onValueChange={setCountry} defaultValue="us">
          <SelectTrigger>
            <SelectValue placeholder="Select a Country" />
          </SelectTrigger>
          <SelectContent>
            {COUNTRIES.map(({ name, code }) => (
              <SelectItem key={code} value={code}>{name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="grid grid-cols-2 gap-2">
          {CATEGORIES.map(cat => (
            <Label key={cat} className="flex items-center gap-2">
              <Checkbox checked={selectedCategories.includes(cat)} onCheckedChange={() => handleCheckbox(cat)} />
              {cat}
            </Label>
          ))}
        </div>
        <Input placeholder="Google News API Key" value={apiKey} onChange={e => setApiKey(e.target.value)} />
        <Input placeholder="Gmail Username" value={gmailUser} onChange={e => setGmailUser(e.target.value)} />
        <Input type="password" placeholder="Gmail App Password" value={gmailPass} onChange={e => setGmailPass(e.target.value)} />
        <Button onClick={handleSubmit}>Fetch & Email News</Button>
      </CardContent>
    </Card>
  )
}
