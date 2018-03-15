import React, { Component } from 'react'
import {Redirect} from 'react-router-dom'
import {load_script, request} from '../utils'
import Error from './Error'

class SignIn extends Component {
  constructor (props) {
    super(props)
    this.state = {
      enabled: false,
      error: null,
      logged_in: false,
    }
    this.sign_in = this.sign_in.bind(this)
  }

  async componentDidMount () {
    this.props.setRootState({nav_title: 'Sign In', status: 'anon'})
    await load_script('https://apis.google.com/js/platform.js')
    window.gapi.load('auth2', () => {
      console.log('auth2')
      this.gauth = window.gapi.auth2.init({
        client_id: process.env.REACT_APP_GOOGLE_SIW_CLIENT_KEY,
        hosted_domain: 'tutorcruncher.com',
        scope: 'profile email',
      })
      this.setState({enabled: true})
    })
  }

  async sign_in () {
    try {
      await this.gauth.signIn()
      await request('/signin/', {id_token: this.gauth.currentUser.get().getAuthResponse().id_token}, 'POST')
      this.props.setRootState({auth: true})
      this.setState({logged_in: true})
    }  catch (err) {
      this.setState({error: `Signin Error: ${err}`})
    }
  }

  render () {
    if (this.state.error) {
      return <Error error={this.state.error}/>
    } else if (this.state.logged_in) {
      return <Redirect to={{
        pathname: '/',
        state: { from: this.props.location }
      }}/>
    } else {
      return (
        <div className="text-center mt-3">
          <button type="button"
                  className="btn btn-primary"
                  disabled={!this.state.enabled}
                  onClick={() => this.sign_in()}>
            Sign in with Google
          </button>
        </div>
      )
    }
  }
}

export default SignIn
